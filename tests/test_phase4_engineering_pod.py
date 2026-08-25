import unittest

from factory.design_pod import (
    AcceptanceCriterion,
    ArchitectureDecision,
    DesignBundle,
    ProductRequirement,
    UXFlow,
)
from factory.engineering_pod import (
    EvidenceManifest,
    EngineeringPlanValidator,
    ImplementationWorkPackage,
    VerificationResult,
)


def design_bundle() -> DesignBundle:
    return DesignBundle(
        mission_id="MISSION-ENG",
        product_summary="Booking product",
        non_goals=(),
        requirements=(
            ProductRequirement("REQ-UI", "User can submit a booking", "MUST"),
            ProductRequirement("REQ-API", "System stores a booking consistently", "MUST"),
        ),
        acceptance_criteria=(
            AcceptanceCriterion("AC-UI", "REQ-UI", "Booking form submits", "frontend test"),
            AcceptanceCriterion("AC-API", "REQ-API", "Booking persists once", "integration test"),
        ),
        architecture_decisions=(
            ArchitectureDecision(
                "ADR-BOOKING",
                "Booking boundary",
                "Use API plus transactional repository",
                "Separate UI from consistency boundary",
                ("REQ-UI", "REQ-API"),
            ),
        ),
        ux_flows=(UXFlow("UX-BOOK", "Book", "user", ("Choose slot", "Submit"), ("REQ-UI",)),),
        risks=("double booking",),
    )


def package(
    package_id: str,
    *,
    discipline: str,
    owner: str,
    requirements: tuple[str, ...],
    scopes: tuple[str, ...],
    depends_on: tuple[str, ...] = (),
    artifacts: tuple[str, ...] = ("code",),
    verification: tuple[str, ...] = ("unit test",),
) -> ImplementationWorkPackage:
    return ImplementationWorkPackage(
        package_id=package_id,
        mission_id="MISSION-ENG",
        owner_agent=owner,
        discipline=discipline,
        objective=f"Implement {package_id}",
        requirement_ids=requirements,
        depends_on=depends_on,
        write_scopes=scopes,
        expected_artifacts=artifacts,
        verification_methods=verification,
    )


class EngineeringPodTests(unittest.TestCase):
    def test_valid_parallel_plan_is_accepted(self):
        packages = (
            package(
                "PKG-FE",
                discipline="FRONTEND",
                owner="A05-FRONTEND",
                requirements=("REQ-UI",),
                scopes=("app/frontend",),
            ),
            package(
                "PKG-BE",
                discipline="BACKEND",
                owner="A06-BACKEND",
                requirements=("REQ-API",),
                scopes=("app/backend",),
            ),
        )
        findings = EngineeringPlanValidator().validate(design=design_bundle(), packages=packages)
        self.assertEqual(findings, ())

    def test_unordered_write_scope_conflict_is_blocked(self):
        packages = (
            package(
                "PKG-FE",
                discipline="FRONTEND",
                owner="A05-FRONTEND",
                requirements=("REQ-UI",),
                scopes=("app",),
            ),
            package(
                "PKG-BE",
                discipline="BACKEND",
                owner="A06-BACKEND",
                requirements=("REQ-API",),
                scopes=("app/backend",),
            ),
        )
        codes = {item.code for item in EngineeringPlanValidator().validate(design=design_bundle(), packages=packages)}
        self.assertIn("UNORDERED_WRITE_SCOPE_CONFLICT", codes)

    def test_dependency_order_allows_overlapping_scope(self):
        packages = (
            package(
                "PKG-DB",
                discipline="DATABASE",
                owner="A07-DATABASE",
                requirements=("REQ-API",),
                scopes=("app/backend/schema",),
            ),
            package(
                "PKG-BE",
                discipline="BACKEND",
                owner="A06-BACKEND",
                requirements=("REQ-UI", "REQ-API"),
                scopes=("app/backend",),
                depends_on=("PKG-DB",),
            ),
        )
        findings = EngineeringPlanValidator().validate(design=design_bundle(), packages=packages)
        self.assertEqual(findings, ())

    def test_unknown_requirement_cycle_and_unowned_must_are_blocked(self):
        packages = (
            package(
                "PKG-A",
                discipline="BACKEND",
                owner="A06-BACKEND",
                requirements=("REQ-NOT-REAL",),
                scopes=("a",),
                depends_on=("PKG-B",),
            ),
            package(
                "PKG-B",
                discipline="FRONTEND",
                owner="A05-FRONTEND",
                requirements=("REQ-UI",),
                scopes=("b",),
                depends_on=("PKG-A",),
            ),
        )
        codes = {item.code for item in EngineeringPlanValidator().validate(design=design_bundle(), packages=packages)}
        self.assertIn("PACKAGE_UNKNOWN_REQUIREMENT", codes)
        self.assertIn("PACKAGE_DEPENDENCY_CYCLE", codes)
        self.assertIn("MUST_WITHOUT_ENGINEERING_OWNER", codes)

    def test_completion_evidence_must_stay_in_scope_and_pass_required_checks(self):
        work = package(
            "PKG-FE",
            discipline="FRONTEND",
            owner="A05-FRONTEND",
            requirements=("REQ-UI", "REQ-API"),
            scopes=("app/frontend",),
            artifacts=("frontend-build",),
            verification=("unit test", "build"),
        )
        evidence = EvidenceManifest(
            package_id="PKG-FE",
            changed_paths=("app/frontend/form.py",),
            produced_artifacts=("frontend-build",),
            verification_results=(
                VerificationResult("VER-1", "unit test", "PASS", "log://unit"),
                VerificationResult("VER-2", "build", "PASS", "log://build"),
            ),
        )
        findings = EngineeringPlanValidator().validate_evidence(package=work, evidence=evidence)
        self.assertEqual(findings, ())

    def test_false_completion_evidence_is_rejected(self):
        work = package(
            "PKG-FE",
            discipline="FRONTEND",
            owner="A05-FRONTEND",
            requirements=("REQ-UI", "REQ-API"),
            scopes=("app/frontend",),
            artifacts=("frontend-build",),
            verification=("unit test", "build"),
        )
        evidence = EvidenceManifest(
            package_id="PKG-FE",
            changed_paths=("app/backend/secret.py",),
            produced_artifacts=("notes",),
            verification_results=(VerificationResult("VER-1", "unit test", "FAIL", "log://unit"),),
        )
        codes = {item.code for item in EngineeringPlanValidator().validate_evidence(package=work, evidence=evidence)}
        self.assertIn("CHANGE_OUTSIDE_WRITE_SCOPE", codes)
        self.assertIn("EXPECTED_ARTIFACT_MISSING", codes)
        self.assertIn("VERIFICATION_FAILED", codes)
        self.assertIn("REQUIRED_VERIFICATION_MISSING", codes)


if __name__ == "__main__":
    unittest.main()
