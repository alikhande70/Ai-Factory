from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from missions.real_estate.contracts import ListingCandidate, ListingState, RightsBasis
from missions.real_estate.integrity import FreshnessPolicy
from missions.real_estate.inventory import InventoryQuery, PublisherTrustEvidence, SQLiteInventoryStore


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def listing(
    *,
    listing_id: str,
    source_ref: str,
    publisher_id: str,
    verified_days_ago: int = 1,
    locality: str = "Central",
    state: ListingState = ListingState.ACTIVE,
    price_minor: int = 100_000_000,
) -> ListingCandidate:
    verified = NOW - timedelta(days=verified_days_ago)
    return ListingCandidate(
        listing_id=listing_id,
        source_ref=source_ref,
        publisher_id=publisher_id,
        rights_basis=RightsBasis.OWNER_SUBMITTED,
        transaction_type="SALE",
        property_type="APARTMENT",
        city="Example City",
        locality=locality,
        geo_cell="geo:123",
        price_minor=price_minor,
        area_sqm=101.0,
        bedrooms=2,
        title="Two bedroom apartment",
        description="Detailed property description",
        image_hashes=("img-a", "img-b", "img-c"),
        source_updated_at=verified - timedelta(days=1),
        last_verified_at=verified,
        state=state,
    )


class Phase10InventoryStoreTests(unittest.TestCase):
    def test_duplicate_sources_are_grouped_without_deleting_source_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                first = listing(listing_id="L1", source_ref="owner://1", publisher_id="P1")
                second = listing(listing_id="L2", source_ref="partner://9", publisher_id="P2")
                canonical_a = store.add_source(first)
                canonical_b = store.add_source(second)
                self.assertEqual(canonical_a, canonical_b)
                self.assertEqual(len(store.source_members(canonical_a)), 2)
                self.assertEqual(store.counts()["source_records"], 2)
                self.assertEqual(store.counts()["canonical_listings"], 1)
            finally:
                store.close()

    def test_readding_same_source_version_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                item = listing(listing_id="L1", source_ref="owner://1", publisher_id="P1")
                first = store.add_source(item)
                second = store.add_source(item)
                self.assertEqual(first, second)
                self.assertEqual(store.counts()["source_records"], 1)
                self.assertEqual(store.counts()["memberships"], 1)
            finally:
                store.close()

    def test_lifecycle_history_is_append_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                canonical = store.add_source(
                    listing(listing_id="L1", source_ref="owner://1", publisher_id="P1")
                )
                store.transition(
                    canonical,
                    ListingState.UNDER_OFFER,
                    reason="PUBLISHER_UPDATE",
                    actor_id="P1",
                )
                store.transition(
                    canonical,
                    ListingState.SOLD,
                    reason="PUBLISHER_CONFIRMED",
                    actor_id="P1",
                )
                events = store.lifecycle(canonical)
                self.assertEqual([row["to_state"] for row in events], ["ACTIVE", "UNDER_OFFER", "SOLD"])
                self.assertEqual(store.canonical(canonical)["state"], "SOLD")
            finally:
                store.close()

    def test_freshness_sweeper_expires_but_does_not_delete_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                canonical = store.add_source(
                    listing(
                        listing_id="OLD",
                        source_ref="owner://old",
                        publisher_id="P1",
                        verified_days_ago=40,
                    )
                )
                expired = store.expire_stale(policy=FreshnessPolicy(max_age_days=30), now=NOW)
                self.assertEqual(expired, (canonical,))
                self.assertEqual(store.canonical(canonical)["state"], "EXPIRED")
                self.assertEqual(store.counts()["source_records"], 1)
            finally:
                store.close()

    def test_restart_recovers_canonical_membership_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/inventory.db"
            first = SQLiteInventoryStore(path)
            canonical = first.add_source(
                listing(listing_id="L1", source_ref="owner://1", publisher_id="P1")
            )
            first.close()

            restarted = SQLiteInventoryStore(path)
            try:
                self.assertEqual(restarted.canonical(canonical)["state"], "ACTIVE")
                self.assertEqual(len(restarted.source_members(canonical)), 1)
                self.assertEqual(len(restarted.lifecycle(canonical)), 1)
                self.assertEqual(restarted.apply_migrations(), 0)
            finally:
                restarted.close()

    def test_publisher_trust_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                with self.assertRaises(ValueError):
                    store.record_publisher_trust(
                        PublisherTrustEvidence("P1", 0.9, (), "A09-SECURITY")
                    )
                evidence = PublisherTrustEvidence(
                    "P1",
                    0.8,
                    ("evidence://identity-check", "evidence://history"),
                    "A09-SECURITY",
                )
                store.record_publisher_trust(evidence)
                self.assertEqual(store.publisher_trust("P1"), evidence)
            finally:
                store.close()

    def test_query_filters_canonical_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                store.add_source(
                    listing(
                        listing_id="L1",
                        source_ref="owner://1",
                        publisher_id="P1",
                        locality="Central",
                        price_minor=80_000_000,
                    )
                )
                store.add_source(
                    listing(
                        listing_id="L2",
                        source_ref="owner://2",
                        publisher_id="P2",
                        locality="North",
                        price_minor=140_000_000,
                    )
                )
                rows = store.query(
                    InventoryQuery(
                        city="Example City",
                        locality="Central",
                        max_price_minor=100_000_000,
                    )
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["locality"], "Central")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
