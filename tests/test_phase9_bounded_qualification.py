from __future__ import annotations

import tempfile
import unittest

from examples.phase4_booking_app import BookingForm, BookingRepository, BookingService, submit_booking
from factory.assurance_pod.contracts import AcceptanceCoverage, AssuranceFinding
from factory.engineering_pod.contracts import ImplementationWorkPackage
from factory.engineering_pod.workspace import WorkspaceAllocator
from factory.evaluations import (
    CaseOutcome,
    EvaluationBaseline,
    EvaluationCase,
    SQLiteEvaluationStore,
    calculate_metrics,
)
from factory.memory import (
    MemoryCandidate,
    MemoryPromotionDecision,
    MemoryPromotionGate,
    SQLiteOrganizationalMemoryStore,
)
from factory.qualification import (
    QualificationEvidence,
    QualificationEvaluator,
    QualificationHarness,
    REQUIRED_DIMENSIONS,
)
from factory.reliability import AttemptRecord, OperationSpec, ReliabilityDecisionEngine
from factory.runtime.catalog import SQLiteRuntimeCatalog
from factory.runtime.intake import MissionIntakeService


MISSION_ID = "MISSION-PHASE9-BOOKING"


def ev(dimension: str, suffix: str) -> QualificationEvidence:
    return QualificationEvidence(dimension, f"evidence://phase9/{suffix}")


class Phase9BoundedQualificationTests(unittest.TestCase):
    def test_factory_path_vs_simple_baseline_under_same_protected_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            booking_db = f"{directory}/booking.db"
            runtime_db = f"{directory}/runtime.db"
            memory_db = f"{directory}/memory.db"
            eval_db = f"{directory}/eval.db"

            def factory_action() -> tuple[QualificationEvidence, ...]:
                intake = MissionIntakeService().prepare(
                    mission_id=MISSION_ID,
                    objective="Build a controlled booking workflow with persistence and safety gates",
                    quality_profile="PRODUCTION",
                    constraints=("No production side effects",),
                )
                self.assertEqual(intake.mission_id, MISSION_ID)

                # Product/architecture/UX are exercised by the Phase 3 suite in the same CI run;
                # this bounded mission carries their traceability reference into qualification.
                evidence = [
                    ev("MISSION_PLANNING", "mission-intake"),
                    ev("ARCHITECTURE_UX", "phase3-design-bundle"),
                ]

                repository = BookingRepository(booking_db)
                service = BookingService(repository)
                created = submit_booking(BookingForm(customer_name="Ada", slot="09:00"), service)
                self.assertEqual(service.get_booking(created.booking_id).customer_name, "Ada")
                evidence.append(ev("FULL_STACK", "booking-roundtrip"))

                self.assertTrue(repository.apply_add_notes_migration())
                self.assertFalse(repository.apply_add_notes_migration())
                self.assertTrue(repository.has_column("notes"))
                evidence.append(ev("MIGRATION", "idempotent-schema-migration"))

                finding = AssuranceFinding(
                    finding_id="SEC-P9-1",
                    category="AUTHORIZATION_BOUNDARY",
                    severity="HIGH",
                    subject_ref="artifact://booking-api",
                    statement="A production booking write must not be exposed without an authorization boundary.",
                    evidence_refs=("test://phase9/protected-action",),
                    remediation="Keep production write behind policy and explicit approval.",
                    blocking=True,
                )
                finding.validate()
                evidence.append(ev("SECURITY", "independent-blocking-finding"))

                coverage = AcceptanceCoverage(
                    criterion_id="AC-BOOKING-ROUNDTRIP",
                    evidence_refs=("test://phase9/booking-roundtrip",),
                )
                coverage.validate()
                evidence.append(ev("QA_REGRESSION", "acceptance-coverage"))

                allocator = WorkspaceAllocator()
                frontend = ImplementationWorkPackage(
                    package_id="P9-FE",
                    mission_id=MISSION_ID,
                    owner_agent="A05-FRONTEND",
                    discipline="FRONTEND",
                    objective="booking form",
                    requirement_ids=("REQ-BOOK",),
                    depends_on=(),
                    write_scopes=("examples/qualification/frontend.py",),
                    expected_artifacts=("frontend",),
                    verification_methods=("unit",),
                )
                backend = ImplementationWorkPackage(
                    package_id="P9-BE",
                    mission_id=MISSION_ID,
                    owner_agent="A06-BACKEND",
                    discipline="BACKEND",
                    objective="booking service",
                    requirement_ids=("REQ-BOOK",),
                    depends_on=(),
                    write_scopes=("examples/qualification/backend.py",),
                    expected_artifacts=("backend",),
                    verification_methods=("unit",),
                )
                fe_workspace = allocator.allocate(frontend)
                be_workspace = allocator.allocate(backend)
                self.assertTrue(set(fe_workspace.write_scopes).isdisjoint(be_workspace.write_scopes))
                evidence.append(ev("PARALLEL_ISOLATION", "non-overlapping-workspaces"))

                operation = OperationSpec(
                    operation_id="P9-EXTERNAL-WRITE",
                    mission_id=MISSION_ID,
                    effect_class="EXTERNAL_WRITE",
                    max_attempts=2,
                    timeout_seconds=5,
                    idempotency_key="phase9:external-write:v1",
                    reconciliation_supported=True,
                )
                decision = ReliabilityDecisionEngine().decide(
                    operation=operation,
                    attempt=AttemptRecord("P9-EXTERNAL-WRITE", 1, "UNKNOWN"),
                )
                self.assertEqual(decision.action, "RECONCILE")
                evidence.append(ev("RELIABILITY_RECONCILE", "unknown-write-reconciles"))

                catalog = SQLiteRuntimeCatalog(runtime_db)
                catalog.propose_action(
                    proposal_id="P9-PROD-WRITE",
                    mission_id=MISSION_ID,
                    action_type="PRODUCTION_WRITE",
                    target="booking-production",
                    protected=True,
                )
                self.assertEqual(catalog.approval_status("P9-PROD-WRITE"), "PENDING")
                catalog.decide_action("P9-PROD-WRITE", approved=True, decided_by="HUMAN-OWNER")
                self.assertEqual(catalog.approval_status("P9-PROD-WRITE"), "APPROVED")
                evidence.append(ev("APPROVAL_GATE", "protected-action-pending-first"))

                catalog.add_artifact(
                    mission_id=MISSION_ID,
                    artifact_id="qualification-state",
                    content="verified",
                    created_by="CONTROL-PLANE",
                )
                restarted = SQLiteRuntimeCatalog(runtime_db)
                self.assertEqual(
                    restarted.latest_artifact(MISSION_ID, "qualification-state")["content_text"],
                    "verified",
                )
                evidence.append(ev("PERSISTENCE_REPLAY", "artifact-recovered-after-restart"))

                candidate = MemoryCandidate(
                    candidate_id="P9-MEM-CAND",
                    mission_id=MISSION_ID,
                    proposed_by="A06-BACKEND",
                    category="LESSON",
                    statement="Unknown external writes reconcile before retry.",
                    evidence_refs=("evidence://phase9/unknown-write-reconciles",),
                    source_ref="artifact://phase9/reliability",
                    source_hash="sha256:phase9-source",
                    source_trust="CANONICAL",
                )
                promotion = MemoryPromotionDecision(
                    candidate_id="P9-MEM-CAND",
                    reviewer_id="A12-RED-TEAM",
                    status="APPROVED",
                    reason="Reusable reliability rule verified in qualification.",
                    verified_evidence_refs=candidate.evidence_refs,
                )
                entry = MemoryPromotionGate().promote(
                    candidate=candidate, decision=promotion, memory_id="P9-MEM-1"
                )
                memory = SQLiteOrganizationalMemoryStore(memory_db)
                try:
                    memory.promote(entry, scope="GLOBAL", observed_source_hash=entry.source_hash)
                    recalled = memory.recall(
                        entry.memory_id,
                        mission_id=None,
                        observed_source_hashes={entry.source_ref: entry.source_hash},
                    )
                    self.assertEqual(recalled.status, "ACTIVE")
                finally:
                    memory.close()
                evidence.append(ev("MEMORY_PROMOTION", "reviewed-lesson-promoted"))

                return tuple(evidence)

            def simple_action() -> tuple[QualificationEvidence, ...]:
                # Same user-visible happy path, intentionally without the Factory control layers.
                simple_db = f"{directory}/simple.db"
                repository = BookingRepository(simple_db)
                service = BookingService(repository)
                created = submit_booking(BookingForm(customer_name="Ada", slot="09:00"), service)
                self.assertIsNotNone(service.get_booking(created.booking_id))
                repository.apply_add_notes_migration()
                return (
                    ev("FULL_STACK", "simple-booking-roundtrip"),
                    ev("MIGRATION", "simple-schema-migration"),
                )

            harness = QualificationHarness()
            factory_result = harness.run_path(path_id="FACTORY", action=factory_action, claimed_complete=True)
            baseline_result = harness.run_path(path_id="SIMPLE", action=simple_action, claimed_complete=True)
            comparison = QualificationEvaluator().compare(factory=factory_result, baseline=baseline_result)

            self.assertEqual(factory_result.covered_dimensions(), REQUIRED_DIMENSIONS)
            self.assertEqual(factory_result.false_completion_rate, 0.0)
            self.assertEqual(baseline_result.false_completion_rate, 1.0)
            self.assertGreater(factory_result.cost_units, baseline_result.cost_units)
            self.assertTrue(comparison.factory_justified)

            cases = tuple(
                EvaluationCase(
                    case_id=dimension,
                    input_ref=f"qualification://{dimension.lower()}",
                    expected_evidence_refs=(f"Q-{dimension}",),
                )
                for dimension in sorted(REQUIRED_DIMENSIONS)
            )
            baseline = EvaluationBaseline(
                baseline_id="PHASE9-QUALIFICATION",
                version=1,
                created_by="A10-QA",
                evaluator_id="A12-EVAL",
                cases=cases,
            )
            eval_store = SQLiteEvaluationStore(eval_db)
            try:
                eval_store.register_baseline(baseline, actor_id="CONTROL-PLANE")
                factory_covered = factory_result.covered_dimensions()
                simple_covered = baseline_result.covered_dimensions()
                factory_metrics = calculate_metrics(
                    baseline,
                    tuple(
                        CaseOutcome(
                            case.case_id,
                            True,
                            (f"Q-{case.case_id}",) if case.case_id in factory_covered else (),
                            1.0 if case.case_id in factory_covered else 0.0,
                            1.0 if case.case_id in factory_covered else 0.0,
                            int(factory_result.latency_ms),
                        )
                        for case in cases
                    ),
                )
                simple_metrics = calculate_metrics(
                    baseline,
                    tuple(
                        CaseOutcome(
                            case.case_id,
                            True,
                            (f"Q-{case.case_id}",) if case.case_id in simple_covered else (),
                            1.0 if case.case_id in simple_covered else 0.0,
                            1.0 if case.case_id in simple_covered else 0.0,
                            int(baseline_result.latency_ms),
                        )
                        for case in cases
                    ),
                )
                eval_store.record_run(
                    run_id="P9-FACTORY",
                    baseline=baseline,
                    worker_id="FACTORY-WORKFORCE",
                    provider_id="CONTROLLED-FACTORY",
                    evaluator_actor_id="A12-EVAL",
                    metrics=factory_metrics,
                )
                eval_store.record_run(
                    run_id="P9-SIMPLE",
                    baseline=baseline,
                    worker_id="SIMPLE-WORKER",
                    provider_id="CONTROLLED-SIMPLE",
                    evaluator_actor_id="A12-EVAL",
                    metrics=simple_metrics,
                )
                summaries = {row["provider_id"]: row for row in eval_store.provider_summary()}
                self.assertEqual(summaries["CONTROLLED-FACTORY"]["mean_false_completion_rate"], 0.0)
                self.assertGreater(
                    summaries["CONTROLLED-SIMPLE"]["mean_false_completion_rate"], 0.0
                )
                self.assertGreaterEqual(summaries["CONTROLLED-FACTORY"]["mean_latency_ms"], 0.0)
                self.assertGreaterEqual(summaries["CONTROLLED-SIMPLE"]["mean_latency_ms"], 0.0)
            finally:
                eval_store.close()


if __name__ == "__main__":
    unittest.main()
