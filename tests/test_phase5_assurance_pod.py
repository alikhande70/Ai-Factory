import json
import tempfile
import unittest

from factory.assurance_pod import (
    AssuranceFinding,
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


def integration() -> IntegrationManifest:
    return IntegrationManifest(
        mission_id="MISSION-ASSURANCE",
        package_order=("PKG-DB", "PKG-BE", "PKG-FE"),
        artifacts=(
            IntegratedArtifact("db", "PKG-DB"),
            IntegratedArtifact("backend", "PKG-BE"),
            IntegratedArtifact("frontend", "PKG-FE"),
        ),
        changed_paths=("app/db.py", "app/backend.py", "app/frontend.py"),
        verification_ids=("VER-DB", "VER-BE", "VER-FE"),
    )


class Worker:
    def __init__(self, agent_id, findings=()):
        self.agent_id = agent_id
        self.findings = findings

    def review(self, *, design, integration):
        return AssuranceReport(
            report_id=f"REPORT-{self.agent_id}",
            mission_id=design.mission_id,
            reviewer_agent=self.agent_id,
            subject_artifact_ref="engineering-integration-manifest",
            findings=self.findings,
            verification_refs=(f"ci://{self.agent_id.lower()}",),
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


if __name__ == "__main__":
    unittest.main()
