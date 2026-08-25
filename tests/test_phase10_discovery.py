from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from missions.real_estate.contracts import ListingCandidate, ListingState, RightsBasis
from missions.real_estate.discovery import (
    IndexEligibilityPolicy,
    NoIndexReason,
    RealEstateDiscoveryService,
)
from missions.real_estate.inventory import SQLiteInventoryStore
from missions.real_estate.presentation import FreshnessPresentation


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def listing(
    *,
    listing_id: str,
    source_ref: str,
    publisher_id: str,
    price_minor: int = 100_000_000,
    verified_at: datetime = NOW,
    state: ListingState = ListingState.ACTIVE,
    title: str = "Two bedroom apartment",
    description: str = "Detailed property description",
) -> ListingCandidate:
    return ListingCandidate(
        listing_id=listing_id,
        source_ref=source_ref,
        publisher_id=publisher_id,
        rights_basis=RightsBasis.OWNER_SUBMITTED,
        transaction_type="SALE",
        property_type="APARTMENT",
        city="Example City",
        locality="Central",
        geo_cell="geo:123",
        price_minor=price_minor,
        area_sqm=100.0,
        bedrooms=2,
        title=title,
        description=description,
        image_hashes=("img-a", "img-b", "img-c"),
        source_updated_at=verified_at - timedelta(minutes=5),
        last_verified_at=verified_at,
        state=state,
    )


class Phase10DiscoveryTests(unittest.TestCase):
    def test_route_identity_is_strict_and_stable(self) -> None:
        canonical = "CAN-0123456789abcdefabcd"
        self.assertEqual(
            RealEstateDiscoveryService.route_for(canonical),
            f"/listing/{canonical}",
        )
        for invalid in ("../admin", "CAN-<script>", "can-0123456789abcdefabcd", "CAN-short"):
            with self.assertRaises(ValueError):
                RealEstateDiscoveryService.route_for(invalid)

    def test_index_policy_fails_closed_for_state_staleness_and_rights(self) -> None:
        eligible = IndexEligibilityPolicy.evaluate(
            state=ListingState.ACTIVE.value,
            freshness=FreshnessPresentation.FRESH,
            rights_bases=(RightsBasis.OWNER_SUBMITTED.value,),
        )
        self.assertTrue(eligible.indexable)
        blocked = IndexEligibilityPolicy.evaluate(
            state=ListingState.SOLD.value,
            freshness=FreshnessPresentation.STALE,
            rights_bases=(RightsBasis.UNAUTHORIZED_SCRAPE.value,),
        )
        self.assertFalse(blocked.indexable)
        self.assertEqual(
            blocked.reasons,
            (
                NoIndexReason.STATE_NOT_PUBLIC,
                NoIndexReason.STALE,
                NoIndexReason.RIGHTS_NOT_PUBLIC,
            ),
        )

    def test_duplicate_sources_produce_one_canonical_discovery_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                first = inventory.add_source(listing(listing_id="L1", source_ref="owner://1", publisher_id="P1"))
                second = inventory.add_source(listing(listing_id="L2", source_ref="partner://2", publisher_id="P2"))
                self.assertEqual(first, second)
                discovery = RealEstateDiscoveryService(inventory, public_base_url="https://example.test")
                entries = discovery.sitemap(now=NOW)
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0].canonical_id, first)
                self.assertEqual(entries[0].loc, f"https://example.test/listing/{first}")
            finally:
                inventory.close()

    def test_stale_and_terminal_inventory_are_excluded_from_sitemap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                stale = inventory.add_source(
                    listing(
                        listing_id="L1",
                        source_ref="owner://1",
                        publisher_id="P1",
                        verified_at=NOW - timedelta(days=40),
                    )
                )
                sold = inventory.add_source(
                    ListingCandidate(
                        **{
                            **listing(
                                listing_id="L2",
                                source_ref="owner://2",
                                publisher_id="P2",
                            ).__dict__,
                            "geo_cell": "geo:999",
                            "title": "Different property",
                            "image_hashes": ("img-x", "img-y", "img-z"),
                        }
                    )
                )
                inventory.transition(sold, ListingState.SOLD, actor_id="TEST", reason="sold")
                discovery = RealEstateDiscoveryService(inventory, public_base_url="https://example.test")
                self.assertFalse(discovery.listing_document(stale, now=NOW).indexable)
                self.assertIn("STALE", discovery.listing_document(stale, now=NOW).noindex_reasons)
                self.assertFalse(discovery.listing_document(sold, now=NOW).indexable)
                self.assertIn("STATE_NOT_PUBLIC", discovery.listing_document(sold, now=NOW).noindex_reasons)
                self.assertEqual(discovery.sitemap(now=NOW), ())
            finally:
                inventory.close()

    def test_metadata_is_plain_text_bounded_and_structured_data_has_no_invented_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                canonical = inventory.add_source(
                    listing(
                        listing_id="L1",
                        source_ref="owner://1",
                        publisher_id="P1",
                        title="<b>Great</b> apartment\x00 " + "x" * 100,
                        description="<script>alert(1)</script> Clean home " + "y" * 200,
                    )
                )
                discovery = RealEstateDiscoveryService(inventory, public_base_url="https://example.test")
                document = discovery.listing_document(canonical, now=NOW)
                self.assertTrue(document.indexable)
                self.assertLessEqual(len(document.title), 70)
                self.assertLessEqual(len(document.description), 160)
                self.assertNotIn("<", document.title + document.description)
                self.assertNotIn("\x00", document.title + document.description)
                self.assertEqual(document.structured_data["@type"], "RealEstateListing")
                self.assertNotIn("fraud", json.dumps(document.structured_data).lower())
                self.assertNotIn("verified", json.dumps(document.structured_data).lower())
                # Currency is not in the canonical model yet, so structured data must
                # not invent a priceCurrency or publish a semantically incomplete Offer.
                self.assertNotIn("priceCurrency", document.structured_data)
                self.assertNotIn("offers", document.structured_data)
            finally:
                inventory.close()

    def test_sitemap_is_stably_sorted_and_lastmod_matches_canonical_significant_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                ids = []
                for index in range(3):
                    item = listing(
                        listing_id=f"L{index}",
                        source_ref=f"owner://{index}",
                        publisher_id=f"P{index}",
                        title=f"Property {index}",
                    )
                    # Ensure distinct canonical fingerprints.
                    item = ListingCandidate(**{**item.__dict__, "geo_cell": f"geo:{index}"})
                    ids.append(inventory.add_source(item))
                discovery = RealEstateDiscoveryService(inventory, public_base_url="https://example.test/catalog")
                entries = discovery.sitemap(now=NOW)
                self.assertEqual(tuple(entry.loc for entry in entries), tuple(sorted(entry.loc for entry in entries)))
                self.assertEqual({entry.canonical_id for entry in entries}, set(ids))
                for entry in entries:
                    self.assertEqual(entry.lastmod, str(inventory.canonical(entry.canonical_id)["updated_at"]))
            finally:
                inventory.close()

    def test_public_base_url_rejects_credentials_query_fragment_and_non_https(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                for invalid in (
                    "http://example.test",
                    "https://user:pass@example.test",
                    "https://example.test?x=1",
                    "https://example.test/#fragment",
                ):
                    with self.assertRaises(ValueError):
                        RealEstateDiscoveryService(inventory, public_base_url=invalid)
            finally:
                inventory.close()

    def test_discovery_schemas_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        document = json.loads((root / "schemas/real-estate-discovery-document.schema.json").read_text())
        sitemap = json.loads((root / "schemas/real-estate-sitemap-entry.schema.json").read_text())
        self.assertFalse(document["additionalProperties"])
        self.assertIn("noindex_reasons", document["required"])
        self.assertEqual(sitemap["properties"]["lastmod"]["format"], "date-time")


if __name__ == "__main__":
    unittest.main()
