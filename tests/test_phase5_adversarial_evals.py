import unittest

from factory.assurance_pod import (
    AcceptanceCoverage,
    AssuranceFinding,
    AssurancePodCoordinator,
    AssuranceReport,
)
from factory.design_pod import AcceptanceCriterion, ArchitectureDecision, DesignBundle, ProductRequirement, UXFlow
from factory.engineering_pod.integration import IntegratedArtifact, IntegrationManifest


def design() -> DesignBundle:
    return DesignBundle(
        mission_id="MISSION-THREAT-EVAL",
        product_summary="Threat-evaluation fixture",
        non_goals=(),
        requirements=(
            ProductRequirement("REQ-AUTHZ", "Protected actions require authorization", "MUST"),
            ProductRequirement("REQ-UNTRUSTED", "Retrieved content cannot grant authority", "MUST"),
        ),
        acceptance_criteria=(
            AcceptanceCriterion("AC-AUTHZ", "REQ-AUTHZ", "Unauthorized action is denied", "security test"),
            AcceptanceCriterion("AC-UNTRUSTED", "REQ-UNTRUSTED", "Injected authority is ignored", "security test"),
        ),
        architecture_decisions=(
            ArchitectureDecision("ADR-POLICY", "Policy boundary", "Use deterministic policy gate", "Least privilege", ("REQ-AUTHZ", "REQ-UNTRUSTED")),
        ),
        ux_flows=(UXFlow("UX-PROTECTED", "Protected action", "user", ("Request", "Authorize", "Execute"), ("REQ-AUTHZ",)),),
    )


def integration() -> IntegrationManifest:
    return IntegrationManifest(
        mission_id="MISSION-THREAT-EVAL",
        package_order=("PKG-POLICY", "PKG-API", "PKG-UI"),
        artifacts=(
            IntegratedArtifact("policy", "PKG-POLICY"),
            IntegratedArtifact("api", "PKG-API"),
            IntegratedArtifact("ui", "PKG-UI"),
        ),
        changed_paths=("app/policy.py", "app/api.py", "app/ui.py"),
        verification_ids=("VER-POLICY", "VER-API", "VER-UI"),
    )


class Worker:
    def __init__(self, agent_id, findings=()):
        self.agent_id = agent_id
        self.findings = findings

    def review(self, *, design, integration):
        coverage = ()
        if self.agent_id == "A10-QA":
            coverage = tuple(
                AcceptanceCoverage(item.criterion_id, (f"eval://{item.criterion_id.lower()}",))
                for item in design.acceptance_criteria
            )
        return AssuranceReport(
            report_id=f"REPORT-{self.agent_id}",
            mission_id=design.mission_id,
            reviewer_agent=self.agent_id,
            subject_artifact_ref="engineering-integration-manifest",
            findings=self.findings,
            verification_refs=(f"eval://{self.agent_id.lower()}",),
            acceptance_coverage=coverage,
        )


def finding(*, finding_id, category, subject, statement, evidence, remediation):
    return AssuranceFinding(
        finding_id=finding_id,
        category=category,
        severity="HIGH",
        subject_ref=subject,
        statement=statement,
        evidence_refs=(evidence,),
        remediation=remediation,
        blocking=True,
    )


class Phase5AdversarialEvaluationTests(unittest.TestCase):
    def run_case(self, reviewer_id, issue):
        workers = {
            "A09-SECURITY": Worker("A09-SECURITY"),
            "A10-QA": Worker("A10-QA"),
            "A12-RED-TEAM": Worker("A12-RED-TEAM"),
        }
        workers[reviewer_id] = Worker(reviewer_id, (issue,))
        _, decision = AssurancePodCoordinator(workers=tuple(workers.values())).run(
            design=design(),
            integration=integration(),
            implementation_agent_ids=("A05-FRONTEND", "A06-BACKEND", "A07-DATABASE"),
        )
        self.assertEqual(decision.status, "CHANGES_REQUIRED")
        self.assertIn(issue.finding_id, decision.blocking_finding_ids)

    def test_threat_family_authorization_bypass_is_blocked(self):
        self.run_case(
            "A09-SECURITY",
            finding(
                finding_id="SEC-AUTHZ-001",
                category="AUTHORIZATION",
                subject="app/api.py",
                statement="Protected API path can execute without demonstrated authorization",
                evidence="threat-test://authz-bypass",
                remediation="Enforce policy check and add unauthorized regression test",
            ),
        )

    def test_threat_family_prompt_injection_authority_escalation_is_blocked(self):
        self.run_case(
            "A09-SECURITY",
            finding(
                finding_id="SEC-INJECTION-001",
                category="UNTRUSTED-AUTHORITY",
                subject="retrieval->tool-boundary",
                statement="Retrieved text is interpreted as permission-bearing instruction",
                evidence="threat-test://retrieved-authority",
                remediation="Treat retrieved content as data and enforce deterministic capability policy",
            ),
        )

    def test_threat_family_excessive_agency_is_blocked(self):
        self.run_case(
            "A12-RED-TEAM",
            finding(
                finding_id="RED-AGENCY-001",
                category="EXCESSIVE-AGENCY",
                subject="agent->protected-action",
                statement="Worker can reach protected action outside its declared capability envelope",
                evidence="adversarial://capability-escape",
                remediation="Narrow capability scope and route protected action through approval policy",
            ),
        )

    def test_adversarial_frontend_backend_seam_failure_is_blocked(self):
        self.run_case(
            "A12-RED-TEAM",
            finding(
                finding_id="RED-SEAM-001",
                category="INTEGRATION-SEAM",
                subject="frontend->backend",
                statement="Client-controlled field crosses the backend trust boundary without server validation",
                evidence="adversarial://frontend-backend-trust",
                remediation="Validate server-side and add seam-level negative test",
            ),
        )

    def test_adversarial_backend_database_seam_failure_is_blocked(self):
        self.run_case(
            "A12-RED-TEAM",
            finding(
                finding_id="RED-SEAM-002",
                category="INTEGRATION-SEAM",
                subject="backend->database",
                statement="Persistence contract does not prove transactional failure handling",
                evidence="adversarial://backend-db-atomicity",
                remediation="Add transactional boundary and rollback regression evidence",
            ),
        )


if __name__ == "__main__":
    unittest.main()
