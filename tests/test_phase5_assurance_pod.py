import json
import tempfile
import unittest

from factory.assurance_pod import (
    AcceptanceCoverage,
    AssuranceFinding,
    AssuranceLifecycle,
    AssurancePodCoordinator,
    AssuranceReport,
    AssuranceValidator,
)
from factory.design_pod import AcceptanceCriterion, ArchitectureDecision, DesignBundle, ProductRequirement, UXFlow
from factory.engineering_pod.integration import IntegratedArtifact, IntegrationManifest
from factory.runtime.catalog import SQLiteRuntimeCatalog


def design() -> DesignBundle:
    return DesignBundle(
        mission_id="MISSION-ASSURANCE",
        product_summary="Assurance fixture",
        non_goals=(),
        requirements=(ProductRequirement("REQ-1", "Safe booking", "MUST"),),
        acceptance_criteria=(AcceptanceCriterion("AC-1", "REQ-1", "Booking succeeds", "integration test"),),
        architecture_decisions=(
            ArchitectureDecision("ADR-1", "Boundary", "Service plus repository", "Testable boundary", ("REQ-1",)),
        ),
        ux_flows=(UXFlow("UX-1", "Book", "user", ("Submit",), ("REQ-1",)),),
        risks=(),
    )


def integration(*, verification_suffix="") -> IntegrationManifest:
    return IntegrationManifest(
        mission_id="MISSION-ASSURANCE",
        package_order=("PKG-DB", "PKG-BE", "PKG-FE"),
        artifacts=(
            IntegratedArtifact("db", "PKG-DB"),
            IntegratedArtifact("backend", "PKG-BE"),
            IntegratedArtifact("frontend", "PKG-FE"),
        ),
        changed_paths=("app/db.py", "app/backend.py", "app/frontend.py"),
        verification_ids=(f"VER-DB{verification_suffix}", "VER-BE", "VER-FE"),
    )


class Worker:
    def __init__(self, agent_id, findings=(), *, cover_acceptance=True):
        self.agent_id = agent_id
        self.findings = findings
        self.cover_acceptance = cover_acceptance

    def review(self, *, design, integration):
        coverage = ()
        if self.agent_id == "A10-QA" and self.cover_acceptance:
            coverage = tuple(
                AcceptanceCoverage(
                    criterion_id=criterion.criterion_id,
                    evidence_refs=(f"test://{criterion.criterion_id.lower()}",),
                )
                for criterion in design.acceptance_criteria
            )
        return AssuranceReport(
            report_id=f"REPORT-{self.agent_id}",
            mission_id=design.mission_id,
            reviewer_agent=self.agent_id,
            subject_artifact_ref="engineering-integration-manifest",
            findings=self.findings,
            verification_refs=(f"ci://{self.agent_id.lower()}",),
            acceptance_coverage=coverage,
        )


class AssurancePodTests(unittest.TestCase):
    def test_clean_independent_reports_produce_persisted_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = SQLiteRuntimeCatalog(f"{directory}/factory.db")
            coordinator = AssurancePodCoordinator(
                workers=(Worker("A09-SECURITY"), Worker("A10-QA"), Worker("A12-RED-TEAM")),
                catalog=catalog,
            )
            reports, decision = coordinator.run(
                design=design(),
                integration=integration(),
                implementation_agent_ids=("A05-FRONTEND", "A06-BACKEND", "A07-DATABASE"),
            )
            self.assertEqual(len(reports), 3)
            self.assertEqual(decision.status, "PASS")
            stored = catalog.latest_artifact("MISSION-ASSURANCE", "assurance-decision")
            payload = json.loads(stored["content_text"])
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(set(payload["reviewer_agents"]), {"A09-SECURITY", "A10-QA", "A12-RED-TEAM"})

    def test_missing_qa_acceptance_coverage_blocks_release(self):
        coordinator = AssurancePodCoordinator(
            workers=(
                Worker("A09-SECURITY"),
                Worker("A10-QA", cover_acceptance=False),
                Worker("A12-RED-TEAM"),
            )
        )
        _, decision = coordinator.run(
            design=design(),
            integration=integration(),
            implementation_agent_ids=("A05-FRONTEND", "A06-BACKEND", "A07-DATABASE"),
        )
        self.assertEqual(decision.status, "CHANGES_REQUIRED")
        self.assertEqual(decision.blocking_finding_ids, ("QA-COVERAGE-AC-1",))

    def test_high_security_finding_blocks_release(self):
        finding = AssuranceFinding(
            finding_id="SEC-001",
            category="AUTHORIZATION",
            severity="HIGH",
            subject_ref="app/backend.py",
            statement="Authorization boundary is not demonstrated",
            evidence_refs=("test://missing-authz",),
            remediation="Add authorization checks and executable regression coverage",
            blocking=True,
        )
        coordinator = AssurancePodCoordinator(
            workers=(
                Worker("A09-SECURITY", (finding,)),
                Worker("A10-QA"),
                Worker("A12-RED-TEAM"),
            )
        )
        _, decision = coordinator.run(
            design=design(),
            integration=integration(),
            implementation_agent_ids=("A05-FRONTEND", "A06-BACKEND", "A07-DATABASE"),
        )
        self.assertEqual(decision.status, "CHANGES_REQUIRED")
        self.assertEqual(decision.blocking_finding_ids, ("SEC-001",))

    def test_reviewer_cannot_be_implementation_agent(self):
        reports = (
            Worker("A09-SECURITY").review(design=design(), integration=integration()),
            Worker("A10-QA").review(design=design(), integration=integration()),
            Worker("A12-RED-TEAM").review(design=design(), integration=integration()),
        )
        with self.assertRaisesRegex(ValueError, "reviewer independence violation"):
            AssuranceValidator().decide(
                mission_id="MISSION-ASSURANCE",
                reports=reports,
                implementation_agent_ids=("A09-SECURITY",),
                required_acceptance_criterion_ids=("AC-1",),
            )

    def test_high_finding_cannot_be_marked_nonblocking(self):
        finding = AssuranceFinding(
            finding_id="SEC-INVALID",
            category="SECURITY",
            severity="CRITICAL",
            subject_ref="artifact",
            statement="Critical issue",
            evidence_refs=("evidence://critical",),
            remediation="Fix it",
            blocking=False,
        )
        with self.assertRaisesRegex(ValueError, "must be blocking"):
            finding.validate()

    def test_blocking_cycle_cannot_release_and_prior_pass_goes_stale_after_change(self):
        coordinator = AssurancePodCoordinator(
            workers=(Worker("A09-SECURITY"), Worker("A10-QA"), Worker("A12-RED-TEAM"))
        )
        _, pass_decision = coordinator.run(
            design=design(),
            integration=integration(),
            implementation_agent_ids=("A05-FRONTEND", "A06-BACKEND", "A07-DATABASE"),
        )
        lifecycle = AssuranceLifecycle(max_attempts=3)
        pass_record = lifecycle.record(
            cycle_id="CYCLE-PASS",
            integration=integration(),
            decision=pass_decision,
        )
        lifecycle.assert_release_ready(record=pass_record, integration=integration())
        with self.assertRaisesRegex(RuntimeError, "subject changed"):
            lifecycle.assert_release_ready(
                record=pass_record,
                integration=integration(verification_suffix="-NEW"),
            )

    def test_remediation_requires_changed_subject_and_stales_previous_cycle(self):
        finding = AssuranceFinding(
            finding_id="RED-001",
            category="INTEGRATION-SEAM",
            severity="HIGH",
            subject_ref="frontend->backend",
            statement="Adversarial seam scenario fails closed-boundary expectation",
            evidence_refs=("adversarial://seam-001",),
            remediation="Correct seam handling and rerun integration verification",
            blocking=True,
        )
        blocked = AssurancePodCoordinator(
            workers=(
                Worker("A09-SECURITY"),
                Worker("A10-QA"),
                Worker("A12-RED-TEAM", (finding,)),
            )
        )
        _, blocked_decision = blocked.run(
            design=design(),
            integration=integration(),
            implementation_agent_ids=("A05-FRONTEND", "A06-BACKEND", "A07-DATABASE"),
        )
        lifecycle = AssuranceLifecycle(max_attempts=2)
        previous = lifecycle.record(
            cycle_id="CYCLE-1",
            integration=integration(),
            decision=blocked_decision,
        )
        with self.assertRaisesRegex(RuntimeError, "blocking assurance findings"):
            lifecycle.assert_release_ready(record=previous, integration=integration())
        request = lifecycle.remediation_request(previous)
        self.assertEqual(request.blocking_finding_ids, ("RED-001",))

        clean = AssurancePodCoordinator(
            workers=(Worker("A09-SECURITY"), Worker("A10-QA"), Worker("A12-RED-TEAM"))
        )
        corrected = integration(verification_suffix="-FIXED")
        _, clean_decision = clean.run(
            design=design(),
            integration=corrected,
            implementation_agent_ids=("A05-FRONTEND", "A06-BACKEND", "A07-DATABASE"),
        )
        stale, current = lifecycle.re_review(
            previous=previous,
            corrected_integration=corrected,
            decision=clean_decision,
            cycle_id="CYCLE-2",
        )
        self.assertTrue(stale.stale)
        self.assertEqual(current.decision_status, "PASS")
        with self.assertRaisesRegex(RuntimeError, "stale assurance"):
            lifecycle.assert_release_ready(record=stale, integration=integration())
        lifecycle.assert_release_ready(record=current, integration=corrected)

    def test_remediation_no_progress_and_budget_are_bounded(self):
        finding = AssuranceFinding(
            finding_id="SEC-LOOP",
            category="SECURITY",
            severity="HIGH",
            subject_ref="backend",
            statement="Issue remains",
            evidence_refs=("test://issue-remains",),
            remediation="Change the subject before re-review",
            blocking=True,
        )
        blocked = AssurancePodCoordinator(
            workers=(
                Worker("A09-SECURITY", (finding,)),
                Worker("A10-QA"),
                Worker("A12-RED-TEAM"),
            )
        )
        _, decision = blocked.run(
            design=design(),
            integration=integration(),
            implementation_agent_ids=("A05-FRONTEND", "A06-BACKEND", "A07-DATABASE"),
        )
        lifecycle = AssuranceLifecycle(max_attempts=1)
        previous = lifecycle.record(cycle_id="CYCLE-1", integration=integration(), decision=decision)
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            lifecycle.re_review(
                previous=previous,
                corrected_integration=integration(verification_suffix="-FIXED"),
                decision=decision,
                cycle_id="CYCLE-2",
            )

        lifecycle = AssuranceLifecycle(max_attempts=2)
        previous = lifecycle.record(cycle_id="CYCLE-1", integration=integration(), decision=decision)
        with self.assertRaisesRegex(RuntimeError, "no subject change"):
            lifecycle.re_review(
                previous=previous,
                corrected_integration=integration(),
                decision=decision,
                cycle_id="CYCLE-2",
            )


if __name__ == "__main__":
    unittest.main()
