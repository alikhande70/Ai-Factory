from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from missions.real_estate import (
    FreshnessPolicy,
    ListingCandidate,
    ListingState,
    RightsBasis,
    SearchSignals,
    completeness_score,
    duplicate_fingerprint,
    ensure_ingestion_allowed,
    freshness_score,
    rank_listing,
    transition_listing_state,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def candidate(
    *,
    listing_id: str = "L-1",
    publisher_id: str = "PUB-1",
    rights_basis: RightsBasis = RightsBasis.OWNER_SUBMITTED,
    state: ListingState = ListingState.ACTIVE,
    verified_days_ago: int = 2,
    locality: str = "Central",
    area_sqm: float = 101.0,
    image_hashes: tuple[str, ...] = ("img-a", "img-b", "img-c"),
) -> ListingCandidate:
    updated = NOW - timedelta(days=3)
    verified = NOW - timedelta(days=verified_days_ago)
    return ListingCandidate(
        listing_id=listing_id,
        source_ref=f"source://{listing_id}",
        publisher_id=publisher_id,
        rights_basis=rights_basis,
        transaction_type="SALE",
        property_type="APARTMENT",
        city="Example City",
        locality=locality,
        geo_cell="geo:123",
        price_minor=100_000_000,
        area_sqm=area_sqm,
        bedrooms=2,
        title="Two bedroom apartment",
        description="Bright apartment with structured, disclosed property details.",
        image_hashes=image_hashes,
        source_updated_at=updated,
        last_verified_at=verified,
        state=state,
    )


class Phase10RealEstateIntegrityTests(unittest.TestCase):
    def test_unauthorized_scrape_is_rejected(self) -> None:
        listing = candidate(rights_basis=RightsBasis.UNAUTHORIZED_SCRAPE)
        with self.assertRaises(PermissionError):
            ensure_ingestion_allowed(listing)

    def test_lifecycle_invalid_transition_fails_closed(self) -> None:
        self.assertEqual(
            transition_listing_state(ListingState.DRAFT, ListingState.ACTIVE),
            ListingState.ACTIVE,
        )
        with self.assertRaises(ValueError):
            transition_listing_state(ListingState.SOLD, ListingState.ACTIVE)

    def test_freshness_expires_deterministically(self) -> None:
        fresh = candidate(verified_days_ago=2)
        stale = candidate(listing_id="L-STALE", verified_days_ago=31)
        policy = FreshnessPolicy(max_age_days=30)
        self.assertGreater(freshness_score(fresh, policy=policy, now=NOW), 0.0)
        self.assertEqual(freshness_score(stale, policy=policy, now=NOW), 0.0)

    def test_duplicate_fingerprint_ignores_source_identity_but_preserves_property_signals(self) -> None:
        first = candidate(listing_id="L-A", publisher_id="PUB-A", area_sqm=101.0)
        second = candidate(listing_id="L-B", publisher_id="PUB-B", area_sqm=102.0)
        different = candidate(
            listing_id="L-C",
            publisher_id="PUB-C",
            locality="Different District",
            area_sqm=102.0,
        )
        self.assertEqual(duplicate_fingerprint(first), duplicate_fingerprint(second))
        self.assertNotEqual(duplicate_fingerprint(first), duplicate_fingerprint(different))

    def test_sparse_listing_has_lower_completeness(self) -> None:
        full = candidate()
        sparse = ListingCandidate(
            **{
                **full.__dict__,
                "listing_id": "L-SPARSE",
                "description": "",
                "image_hashes": ("img-a",),
                "bedrooms": None,
            }
        )
        self.assertGreater(completeness_score(full), completeness_score(sparse))

    def test_expired_or_inactive_inventory_is_not_rank_eligible(self) -> None:
        signals = SearchSignals(
            relevance=0.9,
            freshness=0.8,
            completeness=0.9,
            publisher_trust=0.8,
        )
        decision = rank_listing(candidate(state=ListingState.EXPIRED), signals)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.score, 0.0)

        stale_signals = SearchSignals(
            relevance=1.0,
            freshness=0.0,
            completeness=1.0,
            publisher_trust=1.0,
        )
        stale_decision = rank_listing(candidate(state=ListingState.ACTIVE), stale_signals)
        self.assertFalse(stale_decision.eligible)

    def test_ranking_is_bounded_and_explainable(self) -> None:
        signals = SearchSignals(
            relevance=0.95,
            freshness=0.8,
            completeness=0.9,
            publisher_trust=0.7,
            anomaly_penalty=0.1,
        )
        decision = rank_listing(candidate(), signals)
        self.assertTrue(decision.eligible)
        self.assertGreaterEqual(decision.score, 0.0)
        self.assertLessEqual(decision.score, 1.0)
        self.assertEqual(len(decision.reasons), 5)

    def test_signal_values_outside_bounds_are_rejected(self) -> None:
        signals = SearchSignals(
            relevance=1.1,
            freshness=0.8,
            completeness=0.9,
            publisher_trust=0.7,
        )
        with self.assertRaises(ValueError):
            rank_listing(candidate(), signals)


if __name__ == "__main__":
    unittest.main()
