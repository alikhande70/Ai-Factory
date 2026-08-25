from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from missions.real_estate import (
    AlertEvent,
    DuplicatePriceDivergenceDetector,
    EvidenceCurrency,
    ListingCandidate,
    ListingState,
    RealEstatePresentationService,
    RightsBasis,
    SQLiteInventoryStore,
    SQLiteTrustReviewStore,
    TrustPresentation,
    TrustReviewCoordinator,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def candidate(*, listing_id: str, source_ref: str, publisher_id: str, price: int, when: datetime = NOW) -> ListingCandidate:
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
        price_minor=price,
        area_sqm=100.0,
        bedrooms=2,
        title="Two bedroom apartment",
        description="Detailed property description",
        image_hashes=("img-a", "img-b", "img-c"),
        source_updated_at=when - timedelta(minutes=5),
        last_verified_at=when,
        state=ListingState.ACTIVE,
    )


class Phase10FQualificationTests(unittest.TestCase):
    def test_publisher_to_consumer_to_review_flow_preserves_authority_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            reviews = SQLiteTrustReviewStore(f"{directory}/reviews.db")
            try:
                first = candidate(listing_id="L1", source_ref="owner://1", publisher_id="P1", price=100_000_000)
                submission = RealEstatePresentationService.publisher_submission(first)
                self.assertTrue(submission.rights_accepted)
                self.assertEqual(submission.blocking_codes, ())

                canonical = inventory.add_source(first)
                service = RealEstatePresentationService(inventory, review_store=reviews)
                consumer_before = service.consumer_listing(canonical, now=NOW)
                self.assertEqual(consumer_before.trust_code, TrustPresentation.UNKNOWN)
                self.assertFalse(consumer_before.verification_badge)

                alert = service.alert_status(
                    AlertEvent(
                        event_id="A1",
                        saved_search_id="S1",
                        saved_search_version=1,
                        canonical_id=canonical,
                        owner_id="U1",
                        created_at=NOW.isoformat(),
                    )
                )
                self.assertIn("ALERT_NOT_EXTERNALLY_DELIVERED", alert.message_codes)

                inventory.add_source(
                    candidate(listing_id="L2", source_ref="partner://2", publisher_id="P2", price=160_000_000)
                )
                detector = DuplicatePriceDivergenceDetector()
                coordinator = TrustReviewCoordinator(inventory, reviews, detector)
                case = coordinator.detect_and_queue(canonical)
                assert case is not None

                service = RealEstatePresentationService(inventory, review_store=reviews, detector=detector)
                consumer_review = service.consumer_listing(canonical, now=NOW)
                operator_current = service.operator_review(case)
                self.assertEqual(consumer_review.trust_code, TrustPresentation.NEEDS_REVIEW)
                self.assertFalse(any("FRAUD" in code for code in consumer_review.message_codes))
                self.assertEqual(operator_current.evidence_currency, EvidenceCurrency.CURRENT)

                inventory.add_source(
                    candidate(
                        listing_id="L2",
                        source_ref="partner://2",
                        publisher_id="P2",
                        price=100_000_000,
                        when=NOW + timedelta(hours=1),
                    )
                )
                operator_stale = service.operator_review(case)
                self.assertEqual(operator_stale.evidence_currency, EvidenceCurrency.STALE)

                # Presentation and review evidence never become publisher-trust facts by implication.
                self.assertIsNone(inventory.publisher_trust("P1"))
                self.assertIsNone(inventory.publisher_trust("P2"))
            finally:
                reviews.close()
                inventory.close()


if __name__ == "__main__":
    unittest.main()
