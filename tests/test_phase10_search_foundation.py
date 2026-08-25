from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from missions.real_estate import ListingCandidate, ListingState, RightsBasis
from missions.real_estate.inventory import PublisherTrustEvidence, SQLiteInventoryStore
from missions.real_estate.search import RealEstateSearchService, SearchQuery


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def candidate(
    listing_id: str,
    *,
    source_ref: str | None = None,
    publisher_id: str = "PUB-1",
    title: str = "Modern apartment near park",
    description: str = "Bright two bedroom home with balcony",
    city: str = "Berlin",
    locality: str = "Mitte",
    geo_cell: str = "DE-BE-001-A",
    price_minor: int = 500_000_00,
    verified_days_ago: int = 1,
    image_hash: str | None = None,
) -> ListingCandidate:
    verified = NOW - timedelta(days=verified_days_ago)
    return ListingCandidate(
        listing_id=listing_id,
        source_ref=source_ref or f"feed:{listing_id}",
        publisher_id=publisher_id,
        rights_basis=RightsBasis.PARTNER_FEED,
        transaction_type="SALE",
        property_type="APARTMENT",
        city=city,
        locality=locality,
        geo_cell=geo_cell,
        price_minor=price_minor,
        area_sqm=80.0,
        bedrooms=2,
        title=title,
        description=description,
        image_hashes=(image_hash or f"img-{listing_id}", "img-b", "img-c"),
        source_updated_at=verified - timedelta(hours=1),
        last_verified_at=verified,
        state=ListingState.ACTIVE,
    )


class SearchFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "inventory.sqlite")
        self.store = SQLiteInventoryStore(self.db)
        self.search = RealEstateSearchService(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_text_filter_and_explainable_ranking(self) -> None:
        self.store.add_source(candidate("L1", title="Modern apartment near park"))
        self.store.add_source(candidate("L2", title="Warehouse investment", locality="Kreuzberg", geo_cell="DE-BE-002-A"))
        self.store.record_publisher_trust(
            PublisherTrustEvidence("PUB-1", 0.9, ("EVID-TRUST-1",), "A09-SECURITY")
        )

        page = self.search.search(SearchQuery(text="modern park", city="Berlin"), now=NOW)
        self.assertEqual(len(page.results), 1)
        self.assertEqual(page.results[0].title, "Modern apartment near park")
        self.assertTrue(page.results[0].reasons)
        self.assertGreater(page.results[0].score, 0.0)

    def test_geo_cell_prefix_and_price_filters(self) -> None:
        self.store.add_source(candidate("L1", geo_cell="DE-BE-001-A", price_minor=400_000_00))
        self.store.add_source(candidate("L2", geo_cell="DE-BE-002-A", price_minor=600_000_00))
        self.store.add_source(candidate("L3", city="Hamburg", locality="Altona", geo_cell="DE-HH-001-A", price_minor=450_000_00))

        page = self.search.search(
            SearchQuery(geo_cell_prefix="DE-BE-001", min_price_minor=350_000_00, max_price_minor=450_000_00),
            now=NOW,
        )
        self.assertEqual([r.geo_cell for r in page.results], ["DE-BE-001-A"])

    def test_duplicate_sources_collapse_to_one_search_result(self) -> None:
        first = candidate("L1", source_ref="partner-a:1", publisher_id="PUB-A", image_hash="shared-image")
        second = candidate("L2", source_ref="partner-b:77", publisher_id="PUB-B", image_hash="shared-image")
        self.assertEqual(self.store.add_source(first), self.store.add_source(second))

        page = self.search.search(SearchQuery(city="Berlin"), now=NOW)
        self.assertEqual(len(page.results), 1)
        canonical_id = page.results[0].canonical_id
        self.assertEqual(len(self.store.source_members(canonical_id)), 2)

    def test_stable_cursor_pagination_has_no_duplicates_or_gaps(self) -> None:
        for idx in range(5):
            self.store.add_source(
                candidate(
                    f"L{idx}",
                    geo_cell=f"DE-BE-{idx:03d}-A",
                    verified_days_ago=idx + 1,
                    image_hash=f"unique-{idx}",
                )
            )

        first = self.search.search(SearchQuery(city="Berlin", page_size=2), now=NOW)
        self.assertEqual(len(first.results), 2)
        self.assertIsNotNone(first.next_cursor)
        second = self.search.search(SearchQuery(city="Berlin", page_size=2, cursor=first.next_cursor), now=NOW)
        third = self.search.search(SearchQuery(city="Berlin", page_size=2, cursor=second.next_cursor), now=NOW)

        ids = [r.canonical_id for page in (first, second, third) for r in page.results]
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(set(ids)), 5)
        self.assertIsNone(third.next_cursor)

    def test_equal_score_and_equal_time_use_stable_canonical_tie_breaker(self) -> None:
        for idx in range(6):
            self.store.add_source(
                candidate(
                    f"TIE-{idx}",
                    geo_cell=f"DE-BE-TIE-{idx}",
                    verified_days_ago=1,
                    image_hash=f"tie-{idx}",
                )
            )

        all_ids: list[str] = []
        cursor = None
        while True:
            page = self.search.search(SearchQuery(city="Berlin", page_size=2, cursor=cursor), now=NOW)
            all_ids.extend(result.canonical_id for result in page.results)
            if page.next_cursor is None:
                break
            cursor = page.next_cursor

        self.assertEqual(len(all_ids), 6)
        self.assertEqual(len(set(all_ids)), 6)
        self.assertEqual(all_ids, sorted(all_ids))

    def test_cursor_is_bound_to_query(self) -> None:
        for idx in range(3):
            self.store.add_source(candidate(f"L{idx}", geo_cell=f"DE-BE-{idx}-A", image_hash=f"u-{idx}"))
        first = self.search.search(SearchQuery(city="Berlin", page_size=1), now=NOW)
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.search.search(SearchQuery(city="Hamburg", page_size=1, cursor=first.next_cursor), now=NOW)

    def test_expired_or_stale_listing_is_not_returned(self) -> None:
        self.store.add_source(candidate("STALE", verified_days_ago=31, image_hash="stale"))
        page = self.search.search(SearchQuery(city="Berlin"), now=NOW)
        self.assertEqual(page.results, ())

    def test_unknown_publisher_has_no_invented_trust(self) -> None:
        self.store.add_source(candidate("L1", publisher_id="UNVERIFIED", image_hash="unknown"))
        page = self.search.search(SearchQuery(city="Berlin"), now=NOW)
        reasons = page.results[0].reasons
        self.assertIn("publisher_trust:0.000", reasons)


if __name__ == "__main__":
    unittest.main()
