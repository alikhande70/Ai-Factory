from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest
import xml.etree.ElementTree as ET

from missions.real_estate.contracts import ListingCandidate, ListingState, RightsBasis
from missions.real_estate.discovery import RealEstateDiscoveryService, STRUCTURED_DATA_PROFILE
from missions.real_estate.inventory import SQLiteInventoryStore
from missions.real_estate.presentation import RealEstatePresentationService


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def candidate(*, source_ref: str, listing_id: str, geo_cell: str, when: datetime = NOW) -> ListingCandidate:
    return ListingCandidate(
        listing_id=listing_id,
        source_ref=source_ref,
        publisher_id=f"PUB-{listing_id}",
        rights_basis=RightsBasis.OWNER_SUBMITTED,
        transaction_type="SALE",
        property_type="APARTMENT",
        city="Example City",
        locality="Central",
        geo_cell=geo_cell,
        price_minor=100_000_000,
        area_sqm=100.0,
        bedrooms=2,
        title="<b>Qualified</b> apartment",
        description="Safe canonical description",
        image_hashes=("img-a", "img-b", "img-c"),
        source_updated_at=when - timedelta(minutes=5),
        last_verified_at=when,
        state=ListingState.ACTIVE,
    )


class Phase10GQualificationTests(unittest.TestCase):
    def test_canonical_presentation_to_discovery_to_lifecycle_withdrawal_is_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                canonical = inventory.add_source(candidate(source_ref="owner://1", listing_id="L1", geo_cell="geo:1"))
                presentation = RealEstatePresentationService(inventory)
                discovery = RealEstateDiscoveryService(
                    inventory,
                    public_base_url="https://example.test",
                    presentation=presentation,
                )

                detail = presentation.consumer_listing(canonical, now=NOW)
                document = discovery.listing_document(canonical, now=NOW)
                sitemap = discovery.sitemap(now=NOW)

                self.assertTrue(document.indexable)
                self.assertEqual(document.robots_directive, "index,follow")
                self.assertEqual(document.canonical_id, detail.canonical_id)
                self.assertEqual(document.city, detail.city)
                self.assertEqual(document.locality, detail.locality)
                self.assertEqual(document.price_minor, detail.price_minor)
                self.assertEqual(document.structured_data_profile, STRUCTURED_DATA_PROFILE)
                self.assertEqual(document.structured_data["url"], document.canonical_url)
                self.assertEqual(len(sitemap), 1)

                xml = discovery.render_sitemap_xml(sitemap)
                parsed = ET.fromstring(xml)
                ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                self.assertEqual(parsed.find("s:url/s:loc", ns).text, document.canonical_url)
                self.assertEqual(parsed.find("s:url/s:lastmod", ns).text, document.lastmod)

                # Lifecycle truth changes once, then discovery reflects it without
                # changing route identity or creating a second SEO record.
                inventory.transition(
                    canonical,
                    ListingState.WITHDRAWN,
                    actor_id="QUALIFICATION",
                    reason="publisher withdrew listing",
                )
                withdrawn = discovery.listing_document(canonical, now=NOW)
                self.assertEqual(withdrawn.canonical_url, document.canonical_url)
                self.assertFalse(withdrawn.indexable)
                self.assertEqual(withdrawn.robots_directive, "noindex,follow")
                self.assertIn("STATE_NOT_PUBLIC", withdrawn.noindex_reasons)
                self.assertEqual(discovery.sitemap(now=NOW), ())
            finally:
                inventory.close()

    def test_sitemap_renderer_escapes_url_and_rejects_duplicate_locations(self) -> None:
        from missions.real_estate.discovery import SitemapEntry

        entry = SitemapEntry(
            canonical_id="CAN-0123456789abcdefabcd",
            loc="https://example.test/listing/CAN-0123456789abcdefabcd?x=1&y=2",
            lastmod=NOW.isoformat(),
        )
        xml = RealEstateDiscoveryService.render_sitemap_xml((entry,))
        self.assertIn("&amp;", xml)
        with self.assertRaises(ValueError):
            RealEstateDiscoveryService.render_sitemap_xml((entry, entry))


if __name__ == "__main__":
    unittest.main()
