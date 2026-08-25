from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from missions.real_estate import (
    GeoPoint,
    ListingCandidate,
    ListingState,
    RealEstateSearchService,
    RightsBasis,
    SearchQuery,
    SQLiteGeoIndex,
    SQLiteInventoryStore,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def listing(listing_id: str, *, image_hash: str) -> ListingCandidate:
    return ListingCandidate(
        listing_id=listing_id,
        source_ref=f"feed:{listing_id}",
        publisher_id="PUB-GEO",
        rights_basis=RightsBasis.PARTNER_FEED,
        transaction_type="SALE",
        property_type="APARTMENT",
        city="Berlin",
        locality="Mitte",
        geo_cell="DE-BE-MITTE",
        price_minor=500_000_00,
        area_sqm=80.0,
        bedrooms=2,
        title=f"Apartment {listing_id}",
        description="Geo-index qualification listing",
        image_hashes=(image_hash, "img-b", "img-c"),
        source_updated_at=NOW - timedelta(hours=2),
        last_verified_at=NOW - timedelta(hours=1),
        state=ListingState.ACTIVE,
    )


class GeoIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.geo_path = str(root / "geo.sqlite")
        self.inventory_path = str(root / "inventory.sqlite")
        self.geo = SQLiteGeoIndex(self.geo_path)
        self.inventory = SQLiteInventoryStore(self.inventory_path)

    def tearDown(self) -> None:
        self.geo.close()
        self.inventory.close()
        self.tmp.cleanup()

    def test_coordinate_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "latitude"):
            GeoPoint(91.0, 10.0).validate()
        with self.assertRaisesRegex(ValueError, "longitude"):
            GeoPoint(50.0, 181.0).validate()
        with self.assertRaisesRegex(ValueError, "provided together"):
            ListingCandidate(
                **{**listing("BAD", image_hash="bad").__dict__, "latitude": 52.5, "longitude": None}
            ).validate()

    def test_radius_query_uses_exact_haversine_after_bounding_box(self) -> None:
        self.geo.upsert("A", GeoPoint(52.5200, 13.4050))
        self.geo.upsert("B", GeoPoint(52.5300, 13.4050))
        self.geo.upsert("C", GeoPoint(52.6200, 13.4050))
        hits = self.geo.within_radius(GeoPoint(52.5200, 13.4050), radius_km=2.0)
        self.assertEqual([hit.canonical_id for hit in hits], ["A", "B"])
        self.assertEqual(hits[0].distance_km, 0.0)
        self.assertLess(hits[1].distance_km, 2.0)

    def test_geo_index_restart_and_migration_are_idempotent(self) -> None:
        self.geo.upsert("A", GeoPoint(52.5200, 13.4050))
        self.assertEqual(self.geo.apply_migrations(), 0)
        self.geo.close()

        reopened = SQLiteGeoIndex(self.geo_path)
        try:
            self.assertEqual(reopened.apply_migrations(), 0)
            self.assertEqual(reopened.point("A"), GeoPoint(52.5200, 13.4050))
        finally:
            reopened.close()
        # prevent tearDown from closing the already-closed original connection again
        self.geo = SQLiteGeoIndex(self.geo_path)

    def test_search_radius_filters_canonical_inventory_and_returns_distance(self) -> None:
        near_id = self.inventory.add_source(listing("NEAR", image_hash="near"))
        far_id = self.inventory.add_source(listing("FAR", image_hash="far"))
        self.geo.upsert(near_id, GeoPoint(52.5200, 13.4050))
        self.geo.upsert(far_id, GeoPoint(52.6200, 13.4050))

        service = RealEstateSearchService(self.inventory, geo_index=self.geo)
        page = service.search(
            SearchQuery(
                city="Berlin",
                center_latitude=52.5200,
                center_longitude=13.4050,
                radius_km=2.0,
            ),
            now=NOW,
        )
        self.assertEqual(len(page.results), 1)
        self.assertEqual(page.results[0].canonical_id, near_id)
        self.assertEqual(page.results[0].distance_km, 0.0)

    def test_radius_search_requires_geo_index(self) -> None:
        self.inventory.add_source(listing("L1", image_hash="l1"))
        service = RealEstateSearchService(self.inventory)
        with self.assertRaisesRegex(RuntimeError, "requires a geo index"):
            service.search(
                SearchQuery(
                    center_latitude=52.52,
                    center_longitude=13.405,
                    radius_km=1.0,
                ),
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
