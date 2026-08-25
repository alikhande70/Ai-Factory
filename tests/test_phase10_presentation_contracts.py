from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from missions.real_estate.alerts import AlertEvent
from missions.real_estate.anomalies import DuplicatePriceDivergenceDetector
from missions.real_estate.contracts import ListingCandidate, ListingState, RightsBasis
from missions.real_estate.inventory import PublisherTrustEvidence, SQLiteInventoryStore
from missions.real_estate.presentation import (
    DeliveryPresentation,
    EvidenceCurrency,
    FreshnessPresentation,
    RealEstatePresentationService,
    TrustPresentation,
)
from missions.real_estate.review_queue import SQLiteTrustReviewStore, TrustReviewCoordinator


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def listing(
    *,
    listing_id: str,
    source_ref: str,
    publisher_id: str,
    price_minor: int = 100_000_000,
    rights_basis: RightsBasis = RightsBasis.OWNER_SUBMITTED,
    verified_at: datetime = NOW,
    description: str = "Detailed property description",
    image_hashes: tuple[str, ...] = ("img-a", "img-b", "img-c"),
    state: ListingState = ListingState.ACTIVE,
) -> ListingCandidate:
    return ListingCandidate(
        listing_id=listing_id,
        source_ref=source_ref,
        publisher_id=publisher_id,
        rights_basis=rights_basis,
        transaction_type="SALE",
        property_type="APARTMENT",
        city="Example City",
        locality="Central",
        geo_cell="geo:123",
        price_minor=price_minor,
        area_sqm=100.0,
        bedrooms=2,
        title="Two bedroom apartment",
        description=description,
        image_hashes=image_hashes,
        source_updated_at=verified_at - timedelta(minutes=5),
        last_verified_at=verified_at,
        state=state,
    )


class Phase10PresentationContractTests(unittest.TestCase):
    def test_consumer_projection_exposes_provenance_freshness_without_manufacturing_badge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                canonical = inventory.add_source(listing(listing_id="L1", source_ref="owner://1", publisher_id="P1"))
                inventory.record_publisher_trust(
                    PublisherTrustEvidence(
                        publisher_id="P1",
                        score=0.99,
                        evidence_refs=("EVIDENCE:IDENTITY-1",),
                        verified_by="TRUST-REVIEWER-01",
                    )
                )
                service = RealEstatePresentationService(inventory)
                before = inventory.counts(), inventory.lifecycle(canonical), inventory.publisher_trust("P1")
                projection = service.consumer_listing(canonical, now=NOW)
                after = inventory.counts(), inventory.lifecycle(canonical), inventory.publisher_trust("P1")

                self.assertEqual(projection.freshness_code, FreshnessPresentation.FRESH)
                self.assertEqual(projection.trust_code, TrustPresentation.EVIDENCE_AVAILABLE)
                self.assertFalse(projection.verification_badge)
                self.assertEqual(projection.source_count, 1)
                self.assertEqual(projection.rights_bases, (RightsBasis.OWNER_SUBMITTED.value,))
                self.assertIn("TRUST_EVIDENCE_AVAILABLE", projection.message_codes)
                self.assertEqual(before, after)
            finally:
                inventory.close()

    def test_high_impact_open_review_is_presented_as_needs_review_not_fraud(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            review = SQLiteTrustReviewStore(f"{directory}/review.db")
            try:
                canonical = inventory.add_source(listing(listing_id="L1", source_ref="owner://1", publisher_id="P1", price_minor=100_000_000))
                duplicate = inventory.add_source(listing(listing_id="L2", source_ref="partner://2", publisher_id="P2", price_minor=160_000_000))
                self.assertEqual(canonical, duplicate)
                detector = DuplicatePriceDivergenceDetector()
                case = TrustReviewCoordinator(inventory, review, detector).detect_and_queue(canonical)
                self.assertIsNotNone(case)

                service = RealEstatePresentationService(inventory, review_store=review, detector=detector)
                projection = service.consumer_listing(canonical, now=NOW)
                self.assertEqual(projection.trust_code, TrustPresentation.NEEDS_REVIEW)
                self.assertFalse(projection.verification_badge)
                self.assertIn("TRUST_REVIEW_PENDING", projection.message_codes)
                self.assertFalse(any("FRAUD" in code for code in projection.message_codes))
                self.assertEqual(inventory.publisher_trust("P1"), None)
                self.assertEqual(inventory.publisher_trust("P2"), None)
            finally:
                review.close()
                inventory.close()

    def test_publisher_submission_rejects_unauthorized_rights_without_ingesting(self) -> None:
        candidate = listing(
            listing_id="L-RAW",
            source_ref="scrape://forbidden",
            publisher_id="P-X",
            rights_basis=RightsBasis.UNAUTHORIZED_SCRAPE,
            description="",
            image_hashes=("img-a",),
            state=ListingState.DRAFT,
        )
        projection = RealEstatePresentationService.publisher_submission(candidate)
        self.assertFalse(projection.rights_accepted)
        self.assertEqual(projection.allowed_lifecycle_actions, ())
        self.assertIn("RIGHTS_BASIS_REJECTED", projection.blocking_codes)
        self.assertIn("DISCLOSURE_ACTION_REQUIRED", projection.blocking_codes)
        self.assertIn("DESCRIPTION", projection.missing_disclosures)
        self.assertIn("IMAGES", projection.missing_disclosures)

    def test_publisher_existing_listing_actions_come_from_canonical_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                canonical = inventory.add_source(listing(listing_id="L1", source_ref="owner://1", publisher_id="P1"))
                projection = RealEstatePresentationService(inventory).publisher_listing(canonical)
                self.assertTrue(projection.rights_accepted)
                self.assertEqual(
                    projection.allowed_lifecycle_actions,
                    ("EXPIRED", "RENTED", "SOLD", "UNDER_OFFER", "WITHDRAWN"),
                )
                self.assertEqual(projection.missing_disclosures, ())
            finally:
                inventory.close()

    def test_alert_projection_never_claims_external_delivery_from_internal_outbox(self) -> None:
        event = AlertEvent(
            event_id="ALERT-1",
            saved_search_id="SEARCH-1",
            saved_search_version=1,
            canonical_id="CAN-1",
            owner_id="USER-1",
            created_at=NOW.isoformat(),
            status="PENDING_INTERNAL",
        )
        projection = RealEstatePresentationService.alert_status(event)
        self.assertEqual(projection.delivery_code, DeliveryPresentation.INTERNAL_EVENT_ONLY)
        self.assertIn("ALERT_NOT_EXTERNALLY_DELIVERED", projection.message_codes)

    def test_operator_projection_marks_changed_finding_evidence_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            review = SQLiteTrustReviewStore(f"{directory}/review.db")
            try:
                canonical = inventory.add_source(listing(listing_id="L1", source_ref="owner://1", publisher_id="P1", price_minor=100_000_000))
                inventory.add_source(listing(listing_id="L2", source_ref="partner://2", publisher_id="P2", price_minor=160_000_000))
                detector = DuplicatePriceDivergenceDetector()
                coordinator = TrustReviewCoordinator(inventory, review, detector)
                case = coordinator.detect_and_queue(canonical)
                assert case is not None
                service = RealEstatePresentationService(inventory, review_store=review, detector=detector)
                current = service.operator_review(case)
                self.assertEqual(current.evidence_currency, EvidenceCurrency.CURRENT)

                inventory.add_source(
                    listing(
                        listing_id="L2",
                        source_ref="partner://2",
                        publisher_id="P2",
                        price_minor=100_000_000,
                        verified_at=NOW + timedelta(hours=1),
                    )
                )
                stale = service.operator_review(case)
                self.assertEqual(stale.evidence_currency, EvidenceCurrency.STALE)
                self.assertIn("ANOMALY_EVIDENCE_STALE", stale.message_codes)
            finally:
                review.close()
                inventory.close()

    def test_consumer_stale_and_incomplete_disclosure_codes_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                old = NOW - timedelta(days=40)
                canonical = inventory.add_source(
                    listing(
                        listing_id="L1",
                        source_ref="owner://1",
                        publisher_id="P1",
                        verified_at=old,
                        description="",
                        image_hashes=("img-a",),
                    )
                )
                projection = RealEstatePresentationService(inventory).consumer_listing(canonical, now=NOW)
                self.assertEqual(projection.freshness_code, FreshnessPresentation.STALE)
                self.assertLess(projection.disclosure_score, 1.0)
                self.assertEqual(projection.message_codes[:2], ("LISTING_STALE", "DISCLOSURE_INCOMPLETE"))
            finally:
                inventory.close()

    def test_phase10f_schemas_separate_codes_from_display_strings(self) -> None:
        root = Path(__file__).resolve().parents[1]
        names = (
            "real-estate-consumer-listing.schema.json",
            "real-estate-publisher-submission.schema.json",
            "real-estate-publisher-listing.schema.json",
            "real-estate-operator-review.schema.json",
        )
        for name in names:
            schema = json.loads((root / "schemas" / name).read_text())
            self.assertFalse(schema["additionalProperties"])
        consumer = json.loads((root / "schemas/real-estate-consumer-listing.schema.json").read_text())
        self.assertIn("message_codes", consumer["required"])
        self.assertNotIn("display_message", consumer["properties"])


if __name__ == "__main__":
    unittest.main()
