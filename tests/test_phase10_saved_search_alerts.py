from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from missions.real_estate.alerts import SavedSearch, SavedSearchEvaluator, SQLiteSavedSearchStore
from missions.real_estate.contracts import ListingCandidate, ListingState, RightsBasis
from missions.real_estate.inventory import SQLiteInventoryStore
from missions.real_estate.search import RealEstateSearchService, SearchQuery


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def candidate(
    listing_id: str,
    *,
    city: str = "Berlin",
    state: ListingState = ListingState.ACTIVE,
    title: str | None = None,
    source_ref: str | None = None,
    geo_cell: str | None = None,
    image_hash: str | None = None,
    verified_at: datetime | None = None,
) -> ListingCandidate:
    verified = verified_at or (NOW - timedelta(hours=1))
    return ListingCandidate(
        listing_id=listing_id,
        source_ref=source_ref or f"licensed:{listing_id}",
        publisher_id="PUB-ALERT",
        rights_basis=RightsBasis.LICENSED_DATA,
        transaction_type="SALE",
        property_type="APARTMENT",
        city=city,
        locality="Mitte" if city == "Berlin" else "Altona",
        geo_cell=geo_cell or f"CELL-{listing_id}",
        price_minor=500_000_00,
        area_sqm=80.0,
        bedrooms=2,
        title=title or f"Apartment {listing_id}",
        description="Saved-search qualification listing",
        image_hashes=(image_hash or f"img-{listing_id}", "img-b", "img-c"),
        source_updated_at=verified - timedelta(hours=1),
        last_verified_at=verified,
        state=state,
    )


class SavedSearchAlertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.inventory_path = str(root / "inventory.sqlite")
        self.alert_path = str(root / "alerts.sqlite")
        self.inventory = SQLiteInventoryStore(self.inventory_path)
        self.alerts = SQLiteSavedSearchStore(self.alert_path)
        self.evaluator = SavedSearchEvaluator(self.alerts, RealEstateSearchService(self.inventory))

    def tearDown(self) -> None:
        self.alerts.close()
        self.inventory.close()
        self.tmp.cleanup()

    def _save_berlin(self) -> SavedSearch:
        return self.alerts.save(
            SavedSearch(
                saved_search_id="SS-1",
                owner_id="USER-1",
                name="Berlin apartments",
                query=SearchQuery(city="Berlin", property_type="APARTMENT"),
            )
        )

    def test_first_evaluation_establishes_baseline_without_alert_storm(self) -> None:
        existing_id = self.inventory.add_source(candidate("EXISTING"))
        saved = self._save_berlin()
        self.assertFalse(self.alerts.is_primed(saved.saved_search_id))

        events = self.evaluator.evaluate(saved.saved_search_id, now=NOW)

        self.assertEqual(events, ())
        self.assertTrue(self.alerts.is_primed(saved.saved_search_id))
        self.assertEqual(self.alerts.outbox(), ())
        self.assertEqual(self.evaluator.evaluate(saved.saved_search_id, now=NOW), ())
        self.assertEqual(self.alerts.outbox(), ())
        self.assertTrue(existing_id)

    def test_newly_qualifying_listing_creates_one_internal_event_only(self) -> None:
        self.inventory.add_source(candidate("BASELINE"))
        saved = self._save_berlin()
        self.assertEqual(self.evaluator.evaluate(saved.saved_search_id, now=NOW), ())

        new_id = self.inventory.add_source(candidate("NEW"))
        events = self.evaluator.evaluate(saved.saved_search_id, now=NOW + timedelta(minutes=1))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].canonical_id, new_id)
        self.assertEqual(events[0].status, "PENDING_INTERNAL")
        self.assertEqual(self.alerts.outbox(), events)
        self.assertEqual(self.evaluator.evaluate(saved.saved_search_id, now=NOW + timedelta(minutes=2)), ())
        self.assertEqual(len(self.alerts.outbox()), 1)

    def test_restart_preserves_baseline_and_idempotency(self) -> None:
        self.inventory.add_source(candidate("BASE"))
        saved = self._save_berlin()
        self.evaluator.evaluate(saved.saved_search_id, now=NOW)
        new_id = self.inventory.add_source(candidate("NEW"))
        first = self.evaluator.evaluate(saved.saved_search_id, now=NOW + timedelta(minutes=1))
        self.assertEqual(first[0].canonical_id, new_id)

        self.alerts.close()
        reopened = SQLiteSavedSearchStore(self.alert_path)
        try:
            evaluator = SavedSearchEvaluator(reopened, RealEstateSearchService(self.inventory))
            self.assertTrue(reopened.is_primed(saved.saved_search_id))
            self.assertEqual(evaluator.evaluate(saved.saved_search_id, now=NOW + timedelta(minutes=2)), ())
            self.assertEqual(len(reopened.outbox()), 1)
            self.assertEqual(reopened.apply_migrations(), 0)
        finally:
            reopened.close()
        self.alerts = SQLiteSavedSearchStore(self.alert_path)

    def test_nonmatching_and_inactive_inventory_does_not_alert(self) -> None:
        saved = self._save_berlin()
        self.evaluator.evaluate(saved.saved_search_id, now=NOW)
        self.inventory.add_source(candidate("HAMBURG", city="Hamburg"))
        self.inventory.add_source(candidate("WITHDRAWN", state=ListingState.WITHDRAWN))

        self.assertEqual(self.evaluator.evaluate(saved.saved_search_id, now=NOW + timedelta(minutes=1)), ())
        self.assertEqual(self.alerts.outbox(), ())

    def test_saved_query_edit_increments_version_and_reprimes_without_alert_storm(self) -> None:
        self.inventory.add_source(candidate("BERLIN"))
        saved = self._save_berlin()
        self.evaluator.evaluate(saved.saved_search_id, now=NOW)
        self.inventory.add_source(candidate("HAMBURG", city="Hamburg"))

        edited = self.alerts.save(
            SavedSearch(
                saved_search_id=saved.saved_search_id,
                owner_id=saved.owner_id,
                name="Hamburg apartments",
                query=SearchQuery(city="Hamburg", property_type="APARTMENT"),
            )
        )
        self.assertEqual(edited.version, saved.version + 1)
        self.assertFalse(self.alerts.is_primed(saved.saved_search_id))
        self.assertEqual(self.evaluator.evaluate(saved.saved_search_id, now=NOW + timedelta(minutes=1)), ())
        self.assertTrue(self.alerts.is_primed(saved.saved_search_id))
        self.assertEqual(self.alerts.outbox(), ())

        new_hamburg = self.inventory.add_source(candidate("HAMBURG-NEW", city="Hamburg"))
        events = self.evaluator.evaluate(saved.saved_search_id, now=NOW + timedelta(minutes=2))
        self.assertEqual([event.canonical_id for event in events], [new_hamburg])
        self.assertEqual(events[0].saved_search_version, edited.version)

    def test_prior_version_seen_state_cannot_poison_new_query_version(self) -> None:
        shared = dict(geo_cell="CELL-SHARED", image_hash="img-shared")
        canonical_id = self.inventory.add_source(candidate("V1", title="Garden apartment", **shared))
        original = self.alerts.save(
            SavedSearch("SS-VERSION", "USER-1", "Garden", SearchQuery(text="garden", city="Berlin"))
        )
        self.evaluator.evaluate(original.saved_search_id, now=NOW)

        edited = self.alerts.save(
            SavedSearch("SS-VERSION", "USER-1", "Balcony", SearchQuery(text="balcony", city="Berlin"))
        )
        self.assertEqual(edited.version, original.version + 1)
        self.assertEqual(self.evaluator.evaluate(edited.saved_search_id, now=NOW + timedelta(minutes=1)), ())

        refreshed_id = self.inventory.add_source(
            candidate(
                "V2",
                title="Balcony apartment",
                source_ref="licensed:updated-shared",
                verified_at=NOW + timedelta(minutes=2),
                **shared,
            )
        )
        self.assertEqual(refreshed_id, canonical_id)
        events = self.evaluator.evaluate(edited.saved_search_id, now=NOW + timedelta(minutes=3))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].canonical_id, canonical_id)
        self.assertEqual(events[0].saved_search_version, edited.version)

    def test_disabled_search_does_not_prime_or_emit(self) -> None:
        saved = self.alerts.save(
            SavedSearch(
                saved_search_id="SS-OFF",
                owner_id="USER-1",
                name="Disabled",
                query=SearchQuery(city="Berlin"),
                enabled=False,
            )
        )
        self.inventory.add_source(candidate("NEW"))
        self.assertEqual(self.evaluator.evaluate(saved.saved_search_id, now=NOW), ())
        self.assertFalse(self.alerts.is_primed(saved.saved_search_id))

    def test_saved_search_rejects_cursor_state(self) -> None:
        with self.assertRaisesRegex(ValueError, "pagination cursor"):
            self.alerts.save(
                SavedSearch(
                    saved_search_id="SS-BAD",
                    owner_id="USER-1",
                    name="Bad",
                    query=SearchQuery(city="Berlin", cursor="opaque-cursor"),
                )
            )


if __name__ == "__main__":
    unittest.main()
