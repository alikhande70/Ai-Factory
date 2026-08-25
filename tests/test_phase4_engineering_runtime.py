import unittest

from factory.design_pod import AcceptanceCriterion, ArchitectureDecision, DesignBundle, ProductRequirement, UXFlow
from factory.engineering_pod import (
    EngineeringPlan,
    EngineeringPodCoordinator,
    EvidenceManifest,
    ImplementationWorkPackage,
    VerificationResult,
)


def design_bundle() -> DesignBundle:
    return DesignBundle(
        mission_id="MISSION-RUNTIME",
        product_summary="Booking product",
        non_goals=(),
        requirements=(
            ProductRequirement("REQ-UI", "User can submit a booking", "MUST"),
            ProductRequirement("REQ-API", "Booking is stored consistently", "MUST"),
        ),
        acceptance_criteria=(
            AcceptanceCriterion("AC-UI", "REQ-UI", "Form submits", "frontend test"),
            AcceptanceCriterion("AC-API", "REQ-API", "Booking persists", "integration test"),
        ),
        architecture_decisions=(
            ArchitectureDecision(
                "ADR-BOOKING",
                "Booking boundary",
                "API plus transactional repository",
                "Consistency boundary",
                ("REQ-UI", "REQ-API"),
            ),
        ),
        ux_flows=(UXFlow("UX-BOOK", "Book", "user", ("Choose slot", "Submit"), ("REQ-UI",)),),
        risks=(),
    )


def work(package_id, discipline, owner, requirement_ids, scopes, depends_on=()):
    return ImplementationWorkPackage(
        package_id=package_id,
        mission_id="MISSION-RUNTIME",
        owner_agent=owner,
        discipline=discipline,
        objective=f"Implement {package_id}",
        requirement_ids=requirement_ids,
        depends_on=depends_on,
        write_scopes=scopes,
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
    def __init__(self, agent_id, discipline, calls):
        self.agent_id = agent_id
        self.discipline = discipline
        self.calls = calls

    def implement(self, *, design, package, workspace_id):
        self.calls.append((package.package_id, workspace_id))
        scope = package.write_scopes[0]
        return EvidenceManifest(
            package_id=package.package_id,
            changed_paths=(f"{scope}/impl.py",),
            produced_artifacts=(f"artifact-{package.package_id}",),
            verification_results=(VerificationResult(f"VER-{package.package_id}", "unit test", "PASS", "log://ok"),),
        )


class FixingWorker(Worker):
    def __init__(self, agent_id, discipline, calls):
        super().__init__(agent_id, discipline, calls)
        self.revisions = 0

    def implement(self, *, design, package, workspace_id):
        self.calls.append((package.package_id, workspace_id))
        return EvidenceManifest(
            package_id=package.package_id,
            changed_paths=("outside/scope.py",),
            produced_artifacts=("wrong",),
            verification_results=(VerificationResult("VER-BAD", "unit test", "FAIL", "log://bad"),),
        )

    def revise_implementation(self, *, design, package, workspace_id, previous_evidence, request):
        self.revisions += 1
        scope = package.write_scopes[0]
        return EvidenceManifest(
            package_id=package.package_id,
            changed_paths=(f"{scope}/fixed.py",),
            produced_artifacts=(f"artifact-{package.package_id}",),
            verification_results=(VerificationResult("VER-FIX", "unit test", "PASS", "log://fixed"),),
        )


class EngineeringRuntimeTests(unittest.TestCase):
    def test_dependency_order_and_isolated_workspace_dispatch(self):
        calls = []
        db = work("PKG-DB", "DATABASE", "A07-DATABASE", ("REQ-API",), ("app/db",))
        backend = work(
            "PKG-BE",
            "BACKEND",
            "A06-BACKEND",
            ("REQ-API",),
            ("app/backend",),
            depends_on=("PKG-DB",),
        )
        frontend = work("PKG-FE", "FRONTEND", "A05-FRONTEND", ("REQ-UI",), ("app/frontend",))
        coordinator = EngineeringPodCoordinator(
            planner=Planner(EngineeringPlan((backend, frontend, db))),
            workers=(
                Worker("A05-FRONTEND", "FRONTEND", calls),
                Worker("A06-BACKEND", "BACKEND", calls),
                Worker("A07-DATABASE", "DATABASE", calls),
            ),
        )
        evidence = coordinator.run(design=design_bundle())
        self.assertEqual({item.package_id for item in evidence}, {"PKG-DB", "PKG-BE", "PKG-FE"})
        order = [package_id for package_id, _ in calls]
        self.assertLess(order.index("PKG-DB"), order.index("PKG-BE"))
        self.assertTrue(all(workspace.startswith("MISSION-RUNTIME:") for _, workspace in calls))

    def test_invalid_plan_is_not_executed(self):
        calls = []
        bad = work("PKG-BAD", "FRONTEND", "A05-FRONTEND", ("REQ-NOT-REAL",), ("app/frontend",))
        coordinator = EngineeringPodCoordinator(
            planner=Planner(EngineeringPlan((bad,))),
            workers=(Worker("A05-FRONTEND", "FRONTEND", calls),),
            max_plan_revision_rounds=0,
        )
        with self.assertRaisesRegex(RuntimeError, "engineering_plan_revision_exhausted"):
            coordinator.run(design=design_bundle())
        self.assertEqual(calls, [])

    def test_bad_evidence_can_only_complete_after_bounded_revision(self):
        calls = []
        frontend = work("PKG-FE", "FRONTEND", "A05-FRONTEND", ("REQ-UI", "REQ-API"), ("app/frontend",))
        worker = FixingWorker("A05-FRONTEND", "FRONTEND", calls)
        coordinator = EngineeringPodCoordinator(
            planner=Planner(EngineeringPlan((frontend,))),
            workers=(worker,),
            max_implementation_revision_rounds=1,
        )
        evidence = coordinator.run(design=design_bundle())
        self.assertEqual(worker.revisions, 1)
        self.assertEqual(evidence[0].changed_paths, ("app/frontend/fixed.py",))

    def test_worker_identity_mismatch_is_blocked(self):
        calls = []
        frontend = work("PKG-FE", "FRONTEND", "A05-FRONTEND", ("REQ-UI", "REQ-API"), ("app/frontend",))
        coordinator = EngineeringPodCoordinator(
            planner=Planner(EngineeringPlan((frontend,))),
            workers=(Worker("A05-FRONTEND", "BACKEND", calls),),
        )
        with self.assertRaisesRegex(RuntimeError, "engineering_worker_identity_mismatch"):
            coordinator.run(design=design_bundle())


if __name__ == "__main__":
    unittest.main()
