from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time
import unittest

from missions.real_estate import (
    ListingCandidate,
    ListingState,
    PublisherTrustEvidence,
    RealEstateSearchService,
    RightsBasis,
    SearchQuery,
    SQLiteInventoryStore,
)


FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "real_estate" / "search_relevance_fixture.json"


class SearchQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "inventory.sqlite")
        self.store = SQLiteInventoryStore(self.db)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    @staticmethod
    def _candidate_from_fixture(item: dict[str, object], now: datetime) -> ListingCandidate:
        return ListingCandidate(
            listing_id=str(item["id"]),
            source_ref=f"fixture:{item['id']}",
            publisher_id="PUB-RELEVANCE",
            rights_basis=RightsBasis.LICENSED_DATA,
            transaction_type="SALE",
            property_type="APARTMENT",
            city="Berlin",
            locality=str(item["locality"]),
            geo_cell=str(item["geo_cell"]),
            price_minor=500_000_00,
            area_sqm=80.0,
            bedrooms=2,
            title=str(item["title"]),
            description=str(item["description"]),
            image_hashes=(str(item["image_hash"]), "fixture-b", "fixture-c"),
            source_updated_at=now - timedelta(hours=2),
            last_verified_at=now - timedelta(hours=1),
            state=ListingState.ACTIVE,
        )

    def test_protected_relevance_fixture_ordering(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        now = datetime.fromisoformat(str(fixture["fixed_now"]))
        trust = float(fixture["publisher_trust"])
        canonical_to_listing: dict[str, str] = {}

        for item in fixture["listings"]:
            candidate = self._candidate_from_fixture(item, now)
            canonical_id = self.store.add_source(candidate)
            canonical_to_listing[canonical_id] = candidate.listing_id

        self.store.record_publisher_trust(
            PublisherTrustEvidence(
                publisher_id="PUB-RELEVANCE",
                score=trust,
                evidence_refs=("EVAL:MISSION001-SEARCH-RELEVANCE-V1",),
                verified_by="A10-QA",
            )
        )
        service = RealEstateSearchService(self.store)

        for query_case in fixture["queries"]:
            page = service.search(SearchQuery(text=str(query_case["text"]), city="Berlin"), now=now)
            actual = [canonical_to_listing[result.canonical_id] for result in page.results]
            self.assertEqual(actual, query_case["expected_order"], msg=f"query={query_case['text']}")

    def test_representative_synthetic_search_latency_baseline(self) -> None:
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        for idx in range(500):
            self.store.add_source(
                ListingCandidate(
                    listing_id=f"SYN-{idx:04d}",
                    source_ref=f"synthetic:{idx}",
                    publisher_id="PUB-SYNTH",
                    rights_basis=RightsBasis.LICENSED_DATA,
                    transaction_type="SALE",
                    property_type="APARTMENT" if idx % 2 == 0 else "HOUSE",
                    city="Berlin",
                    locality="Mitte" if idx % 3 == 0 else "Kreuzberg",
                    geo_cell=f"DE-BE-SYN-{idx:04d}",
                    price_minor=300_000_00 + idx * 10_000,
                    area_sqm=60.0 + (idx % 80),
                    bedrooms=(idx % 4) + 1,
                    title=f"Modern apartment synthetic {idx}",
                    description="Representative deterministic benchmark listing near transit and park",
                    image_hashes=(f"syn-{idx}", "syn-b", "syn-c"),
                    source_updated_at=now - timedelta(hours=2),
                    last_verified_at=now - timedelta(hours=1),
                    state=ListingState.ACTIVE,
                )
            )

        service = RealEstateSearchService(self.store)
        query = SearchQuery(
            text="modern park",
            city="Berlin",
            property_type="APARTMENT",
            min_price_minor=300_000_00,
            max_price_minor=400_000_00,
            page_size=20,
        )
        started = time.perf_counter()
        page = service.search(query, now=now)
        elapsed = time.perf_counter() - started

        self.assertEqual(len(page.results), 20)
        # Generous regression guard for the controlled 500-row SQLite fixture;
        # this is not a production SLO and should not be represented as one.
        self.assertLess(elapsed, 2.5, msg=f"controlled search baseline regressed: {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
