from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from missions.real_estate.cards import project_consumer_card
from missions.real_estate.contracts import ListingCandidate, ListingState, RightsBasis
from missions.real_estate.inventory import SQLiteInventoryStore
from missions.real_estate.presentation import RealEstatePresentationService


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


class Phase10FConsumerCardTests(unittest.TestCase):
    def test_card_is_strict_trust_and_freshness_subset_of_detail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                candidate = ListingCandidate(
                    listing_id="L1",
                    source_ref="owner://1",
                    publisher_id="P1",
                    rights_basis=RightsBasis.OWNER_SUBMITTED,
                    transaction_type="SALE",
                    property_type="APARTMENT",
                    city="Example City",
                    locality="Central",
                    geo_cell="geo:123",
                    price_minor=100_000_000,
                    area_sqm=100.0,
                    bedrooms=2,
                    title="Two bedroom apartment",
                    description="Detailed property description",
                    image_hashes=("img-a", "img-b", "img-c"),
                    source_updated_at=NOW - timedelta(minutes=5),
                    last_verified_at=NOW,
                    state=ListingState.ACTIVE,
                )
                canonical = inventory.add_source(candidate)
                service = RealEstatePresentationService(inventory)
                detail = service.consumer_listing(canonical, now=NOW)
                card = project_consumer_card(service, canonical, now=NOW)

                self.assertEqual(card.canonical_id, detail.canonical_id)
                self.assertEqual(card.freshness_code, detail.freshness_code)
                self.assertEqual(card.trust_code, detail.trust_code)
                self.assertEqual(card.verification_badge, detail.verification_badge)
                self.assertEqual(card.message_codes, detail.message_codes)
            finally:
                inventory.close()


if __name__ == "__main__":
    unittest.main()
