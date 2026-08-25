import json
import tempfile
import unittest

from factory.design_pod import AcceptanceCriterion, ArchitectureDecision, DesignBundle, ProductRequirement, UXFlow
from factory.engineering_pod import (
    EngineeringPlan,
    EngineeringPodCoordinator,
    EvidenceManifest,
    ImplementationWorkPackage,
    VerificationResult,
)
from factory.runtime.catalog import SQLiteRuntimeCatalog


def design_bundle():
    return DesignBundle(
        mission_id="MISSION-INTEGRATED",
        product_summary="Booking product",
        non_goals=(),
        requirements=(
            ProductRequirement("REQ-UI", "User can submit a booking", "MUST"),
            ProductRequirement("REQ-DATA", "Booking is stored consistently", "MUST"),
        ),
        acceptance_criteria=(
            AcceptanceCriterion("AC-UI", "REQ-UI", "Form submits", "frontend test"),
            AcceptanceCriterion("AC-DATA", "REQ-DATA", "Booking persists", "integration test"),
        ),
        architecture_decisions=(
            ArchitectureDecision(
                "ADR-BOOKING",
                "Booking boundary",
                "API plus transactional repository",
                "Consistency boundary",
                ("REQ-UI", "REQ-DATA"),
            ),
        ),
        ux_flows=(UXFlow("UX-BOOK", "Book", "user", ("Choose slot", "Submit"), ("REQ-UI",)),),
        risks=(),
    )


def package(package_id, owner, discipline, requirement_ids, scope, depends_on=()):
    return ImplementationWorkPackage(
        package_id=package_id,
        mission_id="MISSION-INTEGRATED",
        owner_agent=owner,
        discipline=discipline,
        objective=f"Implement {package_id}",
        requirement_ids=requirement_ids,
        depends_on=depends_on,
        write_scopes=(scope,),
        expected_artifacts=(f"artifact-{package_id}",),
        verification_methods=("unit test",),
    )


class Planner:
    agent_id = "A01-ORCHESTRATOR"

    def __init__(self, plan):
        self.plan = plan

    def plan_engineering(self, *, design):
        return self.plan


class Worker:
    def __init__(self, agent_id, discipline):
        self.agent_id = agent_id
        self.discipline = discipline

    def implement(self, *, design, package, workspace_id):
        return EvidenceManifest(
            package_id=package.package_id,
            changed_paths=(f"{package.write_scopes[0]}/impl.py",),
            produced_artifacts=(package.expected_artifacts[0],),
            verification_results=(
                VerificationResult(
                    f"VER-{package.package_id}",
                    "unit test",
                    "PASS",
                    f"log://{workspace_id}",
                ),
            ),
        )


class IntegratedRuntimeTests(unittest.TestCase):
    def test_run_integrated_persists_canonical_manifest(self):
        db = package("PKG-DB", "A07-DATABASE", "DATABASE", ("REQ-DATA",), "app/db")
        backend = package(
            "PKG-BE",
            "A06-BACKEND",
            "BACKEND",
            ("REQ-DATA",),
            "app/backend",
            depends_on=("PKG-DB",),
        )
        frontend = package("PKG-FE", "A05-FRONTEND", "FRONTEND", ("REQ-UI",), "app/frontend")

        with tempfile.TemporaryDirectory() as directory:
            catalog = SQLiteRuntimeCatalog(f"{directory}/factory.db")
            coordinator = EngineeringPodCoordinator(
                planner=Planner(EngineeringPlan((backend, frontend, db))),
                workers=(
                    Worker("A05-FRONTEND", "FRONTEND"),
                    Worker("A06-BACKEND", "BACKEND"),
                    Worker("A07-DATABASE", "DATABASE"),
                ),
                catalog=catalog,
            )
            evidence, integration = coordinator.run_integrated(design=design_bundle())

            self.assertEqual({item.package_id for item in evidence}, {"PKG-DB", "PKG-BE", "PKG-FE"})
            self.assertLess(integration.package_order.index("PKG-DB"), integration.package_order.index("PKG-BE"))
            self.assertEqual(set(coordinator.workspace_assignments), {"PKG-DB", "PKG-BE", "PKG-FE"})
            self.assertEqual(
                coordinator.workspace_assignments["PKG-FE"].branch_name,
                "factory/mission-integrated/pkg-fe",
            )

            stored = catalog.latest_artifact("MISSION-INTEGRATED", "engineering-integration-manifest")
            payload = json.loads(stored["content_text"])
            self.assertEqual(payload["mission_id"], "MISSION-INTEGRATED")
            self.assertEqual(tuple(payload["package_order"]), integration.package_order)
            self.assertEqual(stored["media_type"], "application/vnd.ai-factory.engineering-integration+json")


if __name__ == "__main__":
    unittest.main()
