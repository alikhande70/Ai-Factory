import unittest

from factory.engineering_pod import (
    EngineeringIntegrationValidator,
    EvidenceManifest,
    ImplementationWorkPackage,
    VerificationResult,
)


def work(package_id, owner, discipline, scope, depends_on=(), artifact_name=None):
    expected_artifact = artifact_name or f"artifact-{package_id}"
    return ImplementationWorkPackage(
        package_id=package_id,
        mission_id="MISSION-I",
        owner_agent=owner,
        discipline=discipline,
        objective=f"Implement {package_id}",
        requirement_ids=("REQ-1",),
        depends_on=depends_on,
        write_scopes=(scope,),
        expected_artifacts=(expected_artifact,),
        verification_methods=("unit test",),
    )


def evidence(package, *, path=None, artifact=None, verification_id=None):
    scope = package.write_scopes[0]
    return EvidenceManifest(
        package_id=package.package_id,
        changed_paths=(path or f"{scope}/impl.py",),
        produced_artifacts=(artifact or package.expected_artifacts[0],),
        verification_results=(
            VerificationResult(
                verification_id or f"VER-{package.package_id}",
                "unit test",
                "PASS",
                "log://pass",
            ),
        ),
    )


class EngineeringIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.validator = EngineeringIntegrationValidator()
        self.db = work("PKG-DB", "A07-DATABASE", "DATABASE", "app/db")
        self.backend = work(
            "PKG-BE",
            "A06-BACKEND",
            "BACKEND",
            "app/backend",
            depends_on=("PKG-DB",),
        )

    def test_valid_integration_is_traceable_and_dependency_ordered(self):
        result = self.validator.integrate(
            mission_id="MISSION-I",
            packages=(self.backend, self.db),
            evidence=(evidence(self.backend), evidence(self.db)),
            package_order=("PKG-DB", "PKG-BE"),
        )
        self.assertEqual(result.package_order, ("PKG-DB", "PKG-BE"))
        self.assertEqual(
            {(item.artifact_name, item.owner_package_id) for item in result.artifacts},
            {("artifact-PKG-DB", "PKG-DB"), ("artifact-PKG-BE", "PKG-BE")},
        )
        self.assertEqual(set(result.verification_ids), {"VER-PKG-DB", "VER-PKG-BE"})

    def test_dependency_cannot_integrate_after_dependent_package(self):
        with self.assertRaisesRegex(ValueError, "must integrate before"):
            self.validator.integrate(
                mission_id="MISSION-I",
                packages=(self.backend, self.db),
                evidence=(evidence(self.backend), evidence(self.db)),
                package_order=("PKG-BE", "PKG-DB"),
            )

    def test_missing_or_duplicate_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "evidence mismatch"):
            self.validator.integrate(
                mission_id="MISSION-I",
                packages=(self.backend, self.db),
                evidence=(evidence(self.db),),
                package_order=("PKG-DB", "PKG-BE"),
            )
        with self.assertRaisesRegex(ValueError, "duplicate evidence"):
            self.validator.integrate(
                mission_id="MISSION-I",
                packages=(self.db,),
                evidence=(evidence(self.db), evidence(self.db)),
                package_order=("PKG-DB",),
            )

    def test_ambiguous_artifact_ownership_is_rejected(self):
        db = work("PKG-DB", "A07-DATABASE", "DATABASE", "app/db", artifact_name="shared-build")
        frontend = work(
            "PKG-FE",
            "A05-FRONTEND",
            "FRONTEND",
            "app/frontend",
            artifact_name="shared-build",
        )
        with self.assertRaisesRegex(ValueError, "ambiguous artifact ownership"):
            self.validator.integrate(
                mission_id="MISSION-I",
                packages=(db, frontend),
                evidence=(evidence(db), evidence(frontend)),
                package_order=("PKG-DB", "PKG-FE"),
            )

    def test_same_changed_path_cannot_be_claimed_by_two_packages(self):
        later = work(
            "PKG-LATER",
            "A06-BACKEND",
            "BACKEND",
            "app",
            depends_on=("PKG-DB",),
        )
        same_path = "app/db/shared.py"
        with self.assertRaisesRegex(ValueError, "same path changed by multiple packages"):
            self.validator.integrate(
                mission_id="MISSION-I",
                packages=(self.db, later),
                evidence=(
                    evidence(self.db, path=same_path),
                    evidence(later, path=same_path),
                ),
                package_order=("PKG-DB", "PKG-LATER"),
            )


if __name__ == "__main__":
    unittest.main()
