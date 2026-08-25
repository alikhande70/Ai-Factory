from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from missions.real_estate.anomalies import DuplicatePriceDivergenceDetector, FindingSeverity
from missions.real_estate.contracts import ListingCandidate, ListingState, RightsBasis
from missions.real_estate.inventory import SQLiteInventoryStore
from missions.real_estate.review_queue import (
    ReviewOutcome,
    ReviewStatus,
    SQLiteTrustReviewStore,
    StaleFindingError,
    TrustReviewCoordinator,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def listing(
    *,
    listing_id: str,
    source_ref: str,
    publisher_id: str,
    price_minor: int,
    verified_at: datetime = NOW,
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
        title="Two bedroom apartment",
        description="Detailed property description",
        image_hashes=("img-a", "img-b", "img-c"),
        source_updated_at=verified_at - timedelta(minutes=5),
        last_verified_at=verified_at,
        state=ListingState.ACTIVE,
    )


def seed_divergence(store: SQLiteInventoryStore) -> str:
    canonical = store.add_source(
        listing(
            listing_id="L1",
            source_ref="owner://1",
            publisher_id="P1",
            price_minor=100_000_000,
        )
    )
    second = store.add_source(
        listing(
            listing_id="L2",
            source_ref="partner://2",
            publisher_id="P2",
            price_minor=160_000_000,
        )
    )
    if canonical != second:
        raise AssertionError("fixture sources must collapse to one canonical listing")
    return canonical


class Phase10TrustReviewTests(unittest.TestCase):
    def test_detector_emits_evidence_not_a_fraud_or_trust_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                canonical = seed_divergence(inventory)
                before = inventory.canonical(canonical)
                finding = DuplicatePriceDivergenceDetector().detect(inventory, canonical)
                self.assertIsNotNone(finding)
                assert finding is not None
                self.assertEqual(finding.severity, FindingSeverity.HIGH)
                self.assertEqual(len(finding.source_version_ids), 2)
                self.assertEqual(len(finding.evidence_refs), 2)
                self.assertEqual(len(finding.evidence_fingerprint), 64)
                self.assertEqual(inventory.publisher_trust("P1"), None)
                self.assertEqual(inventory.publisher_trust("P2"), None)
                after = inventory.canonical(canonical)
                self.assertEqual(after["state"], before["state"])
                self.assertEqual(after["active_source_version_id"], before["active_source_version_id"])
            finally:
                inventory.close()

    def test_queue_is_idempotent_and_survives_restart_with_audit_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            review_path = f"{directory}/review.db"
            try:
                canonical = seed_divergence(inventory)
                detector = DuplicatePriceDivergenceDetector()
                finding = detector.detect(inventory, canonical)
                assert finding is not None

                first = SQLiteTrustReviewStore(review_path)
                case_a = first.queue(finding)
                case_b = first.queue(finding)
                self.assertEqual(case_a.case_id, case_b.case_id)
                self.assertEqual(case_a.status, ReviewStatus.OPEN)
                self.assertEqual(len(first.events(case_a.case_id)), 1)
                self.assertTrue(first.verify_audit_chain(case_a.case_id))
                first.close()

                restarted = SQLiteTrustReviewStore(review_path)
                try:
                    recovered = restarted.get(case_a.case_id)
                    self.assertEqual(recovered.finding.finding_id, finding.finding_id)
                    self.assertEqual(recovered.finding.evidence_fingerprint, finding.evidence_fingerprint)
                    self.assertTrue(restarted.verify_audit_chain(case_a.case_id))
                    self.assertEqual(restarted.apply_migrations(), 0)
                finally:
                    restarted.close()
            finally:
                inventory.close()

    def test_high_impact_review_must_be_independent_from_detector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            review = SQLiteTrustReviewStore(f"{directory}/review.db")
            try:
                canonical = seed_divergence(inventory)
                detector = DuplicatePriceDivergenceDetector()
                finding = detector.detect(inventory, canonical)
                assert finding is not None
                case = review.queue(finding)
                with self.assertRaises(PermissionError):
                    review.start_review(case.case_id, reviewer_id=detector.detector_id)
                started = review.start_review(case.case_id, reviewer_id="TRUST-REVIEWER-01")
                self.assertEqual(started.status, ReviewStatus.IN_REVIEW)
                self.assertEqual(started.assigned_reviewer, "TRUST-REVIEWER-01")
            finally:
                review.close()
                inventory.close()

    def test_false_positive_is_dismissed_with_evidence_and_no_domain_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            review = SQLiteTrustReviewStore(f"{directory}/review.db")
            try:
                canonical = seed_divergence(inventory)
                before = inventory.canonical(canonical)
                detector = DuplicatePriceDivergenceDetector()
                finding = detector.detect(inventory, canonical)
                assert finding is not None
                case = review.queue(finding)
                review.start_review(case.case_id, reviewer_id="TRUST-REVIEWER-01")
                resolved = review.resolve(
                    case.case_id,
                    reviewer_id="TRUST-REVIEWER-01",
                    outcome=ReviewOutcome.FALSE_POSITIVE,
                    evidence_refs=("EVIDENCE:OPERATOR-CHECK-001",),
                    note="Independent source confirmation shows an intentional asking-price variation.",
                )
                self.assertEqual(resolved.status, ReviewStatus.DISMISSED)
                self.assertEqual(inventory.canonical(canonical)["state"], before["state"])
                self.assertEqual(inventory.publisher_trust("P1"), None)
                self.assertTrue(review.verify_audit_chain(case.case_id))
            finally:
                review.close()
                inventory.close()

    def test_confirmed_anomaly_requires_evidence_and_still_cannot_mutate_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            review = SQLiteTrustReviewStore(f"{directory}/review.db")
            try:
                canonical = seed_divergence(inventory)
                before = inventory.canonical(canonical)
                detector = DuplicatePriceDivergenceDetector()
                coordinator = TrustReviewCoordinator(inventory, review, detector)
                case = coordinator.detect_and_queue(canonical)
                assert case is not None
                review.start_review(case.case_id, reviewer_id="TRUST-REVIEWER-01")
                with self.assertRaises(ValueError):
                    coordinator.resolve_current(
                        case.case_id,
                        reviewer_id="TRUST-REVIEWER-01",
                        outcome=ReviewOutcome.CONFIRMED_ANOMALY,
                        evidence_refs=(),
                        note="Checked independently.",
                    )
                resolved = coordinator.resolve_current(
                    case.case_id,
                    reviewer_id="TRUST-REVIEWER-01",
                    outcome=ReviewOutcome.CONFIRMED_ANOMALY,
                    evidence_refs=("EVIDENCE:CALLBACK-001", "EVIDENCE:SOURCE-SNAPSHOT-001"),
                    note="Independent review confirms the source records disagree materially.",
                )
                self.assertEqual(resolved.status, ReviewStatus.RESOLVED)
                after = inventory.canonical(canonical)
                self.assertEqual(after["state"], before["state"])
                self.assertEqual(after["active_source_version_id"], before["active_source_version_id"])
                self.assertEqual(inventory.publisher_trust("P1"), None)
                self.assertEqual(inventory.publisher_trust("P2"), None)
            finally:
                review.close()
                inventory.close()

    def test_changed_source_evidence_blocks_confirmed_resolution_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            review = SQLiteTrustReviewStore(f"{directory}/review.db")
            try:
                canonical = seed_divergence(inventory)
                detector = DuplicatePriceDivergenceDetector()
                coordinator = TrustReviewCoordinator(inventory, review, detector)
                case = coordinator.detect_and_queue(canonical)
                assert case is not None
                review.start_review(case.case_id, reviewer_id="TRUST-REVIEWER-01")

                inventory.add_source(
                    listing(
                        listing_id="L2",
                        source_ref="partner://2",
                        publisher_id="P2",
                        price_minor=100_000_000,
                        verified_at=NOW + timedelta(hours=1),
                    )
                )
                with self.assertRaises(StaleFindingError):
                    coordinator.resolve_current(
                        case.case_id,
                        reviewer_id="TRUST-REVIEWER-01",
                        outcome=ReviewOutcome.CONFIRMED_ANOMALY,
                        evidence_refs=("EVIDENCE:OLD-SNAPSHOT",),
                        note="Would be stale if accepted.",
                    )
                self.assertEqual(review.get(case.case_id).status, ReviewStatus.IN_REVIEW)
            finally:
                review.close()
                inventory.close()

    def test_audit_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            review = SQLiteTrustReviewStore(f"{directory}/review.db")
            try:
                canonical = seed_divergence(inventory)
                finding = DuplicatePriceDivergenceDetector().detect(inventory, canonical)
                assert finding is not None
                case = review.queue(finding)
                self.assertTrue(review.verify_audit_chain(case.case_id))
                with review._connection:
                    review._connection.execute(
                        "UPDATE review_events SET note = ? WHERE case_id = ?",
                        ("tampered", case.case_id),
                    )
                self.assertFalse(review.verify_audit_chain(case.case_id))
            finally:
                review.close()
                inventory.close()

    def test_phase10e_machine_readable_schemas_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        anomaly = json.loads((root / "schemas/real-estate-anomaly-finding.schema.json").read_text())
        review = json.loads((root / "schemas/real-estate-trust-review.schema.json").read_text())
        self.assertIn("evidence_fingerprint", anomaly["required"])
        self.assertEqual(anomaly["properties"]["severity"]["enum"], ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        self.assertEqual(review["properties"]["status"]["enum"], ["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"])


if __name__ == "__main__":
    unittest.main()
