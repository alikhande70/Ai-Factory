import json
import tempfile
import unittest

from factory.design_pod import (
    AcceptanceCriterion,
    ArchitectureDecision,
    ArchitectureDesignOutput,
    DesignPodCoordinator,
    ProductDesignOutput,
    ProductRequirement,
    RevisionRequest,
    UXDesignOutput,
    UXFlow,
)
from factory.runtime.catalog import SQLiteRuntimeCatalog


class ProductWorker:
    agent_id = "A02-PRODUCT"

    def design_product(self, *, mission_id: str, objective: str) -> ProductDesignOutput:
        return ProductDesignOutput(
            product_summary=objective,
            non_goals=("payments",),
            requirements=(ProductRequirement("REQ-1", "User can create a booking", "MUST"),),
            acceptance_criteria=(
                AcceptanceCriterion("AC-1", "REQ-1", "Valid booking is created", "integration test"),
            ),
            assumptions=("authenticated user",),
            risks=("double booking",),
        )


class ArchitectureWorker:
    agent_id = "A03-ARCH"

    def design_architecture(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
    ) -> ArchitectureDesignOutput:
        return ArchitectureDesignOutput(
            decisions=(
                ArchitectureDecision(
                    "ADR-1",
                    "Transactional booking",
                    "Use one transactional application service",
                    "Protect slot consistency",
                    ("REQ-1",),
                ),
            ),
            risks=("database contention",),
        )


class UXWorkerImpl:
    agent_id = "A04-UX"

    def design_ux(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
    ) -> UXDesignOutput:
        return UXDesignOutput(
            flows=(
                UXFlow(
                    "UX-1",
                    "Create booking",
                    "user",
                    ("Choose slot", "Confirm", "See result"),
                    ("REQ-1",),
                ),
            ),
            risks=("slot expires during confirmation",),
        )


class RevisingArchitectureWorker(ArchitectureWorker):
    def __init__(self) -> None:
        self.revision_requests: list[RevisionRequest] = []

    def design_architecture(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
    ) -> ArchitectureDesignOutput:
        return ArchitectureDesignOutput(
            decisions=(ArchitectureDecision("ADR-X", "Broken", "None", "Invalid reference", ("REQ-X",)),)
        )

    def revise_architecture(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
        architecture: ArchitectureDesignOutput,
        request: RevisionRequest,
    ) -> ArchitectureDesignOutput:
        self.revision_requests.append(request)
        return super().design_architecture(mission_id=mission_id, objective=objective, product=product)


class StubbornArchitectureWorker(RevisingArchitectureWorker):
    def revise_architecture(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
        architecture: ArchitectureDesignOutput,
        request: RevisionRequest,
    ) -> ArchitectureDesignOutput:
        self.revision_requests.append(request)
        return architecture


class InvalidProductWorker(ProductWorker):
    def __init__(self) -> None:
        self.revision_requests: list[RevisionRequest] = []

    def design_product(self, *, mission_id: str, objective: str) -> ProductDesignOutput:
        return ProductDesignOutput(
            product_summary=objective,
            non_goals=(),
            requirements=(ProductRequirement("REQ-1", "User can create a booking", "MUST"),),
            acceptance_criteria=(),
            risks=("missing acceptance coverage",),
        )

    def revise_product(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
        request: RevisionRequest,
    ) -> ProductDesignOutput:
        self.revision_requests.append(request)
        return super().design_product(mission_id=mission_id, objective=objective)


class CountingArchitectureWorker(ArchitectureWorker):
    def __init__(self) -> None:
        self.calls = 0

    def design_architecture(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
    ) -> ArchitectureDesignOutput:
        self.calls += 1
        return super().design_architecture(mission_id=mission_id, objective=objective, product=product)


class CountingUXWorker(UXWorkerImpl):
    def __init__(self) -> None:
        self.calls = 0

    def design_ux(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
    ) -> UXDesignOutput:
        self.calls += 1
        return super().design_ux(mission_id=mission_id, objective=objective, product=product)


class DesignPodRuntimeTests(unittest.TestCase):
    def test_raw_mission_becomes_build_ready_persisted_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = SQLiteRuntimeCatalog(f"{directory}/runtime.db")
            coordinator = DesignPodCoordinator(
                product_worker=ProductWorker(),
                architecture_worker=ArchitectureWorker(),
                ux_worker=UXWorkerImpl(),
                catalog=catalog,
            )
            bundle = coordinator.run(mission_id="MISSION-E2E-1", objective="A reliable booking app")
            self.assertEqual(bundle.product_summary, "A reliable booking app")
            self.assertEqual(bundle.risks, ("double booking", "database contention", "slot expires during confirmation"))

            stored = catalog.latest_artifact("MISSION-E2E-1", "design-bundle")
            payload = json.loads(stored["content_text"])
            self.assertEqual(payload["mission_id"], "MISSION-E2E-1")
            self.assertEqual(payload["requirements"][0]["requirement_id"], "REQ-1")
            self.assertEqual(stored["created_by"], "DESIGN-POD")

    def test_architecture_finding_routes_only_to_architecture_revision(self):
        worker = RevisingArchitectureWorker()
        coordinator = DesignPodCoordinator(
            product_worker=ProductWorker(), architecture_worker=worker, ux_worker=UXWorkerImpl()
        )
        bundle = coordinator.run(mission_id="MISSION-REV-1", objective="A booking app")
        self.assertEqual(bundle.architecture_decisions[0].decision_id, "ADR-1")
        self.assertEqual(len(worker.revision_requests), 1)
        self.assertEqual(worker.revision_requests[0].round_number, 1)
        self.assertEqual(
            tuple(item.code for item in worker.revision_requests[0].findings),
            ("ARCHITECTURE_UNKNOWN_REQUIREMENT",),
        )

    def test_product_revision_regenerates_all_downstream_design(self):
        product = InvalidProductWorker()
        architecture = CountingArchitectureWorker()
        ux = CountingUXWorker()
        coordinator = DesignPodCoordinator(
            product_worker=product,
            architecture_worker=architecture,
            ux_worker=ux,
        )
        bundle = coordinator.run(mission_id="MISSION-REV-2", objective="A booking app")
        self.assertEqual(bundle.acceptance_criteria[0].requirement_id, "REQ-1")
        self.assertEqual(len(product.revision_requests), 1)
        self.assertEqual(architecture.calls, 2)
        self.assertEqual(ux.calls, 2)

    def test_no_progress_revision_fails_without_persisting(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = SQLiteRuntimeCatalog(f"{directory}/runtime.db")
            worker = StubbornArchitectureWorker()
            coordinator = DesignPodCoordinator(
                product_worker=ProductWorker(),
                architecture_worker=worker,
                ux_worker=UXWorkerImpl(),
                catalog=catalog,
            )
            with self.assertRaisesRegex(RuntimeError, "design_revision_no_progress:ARCHITECTURE_UNKNOWN_REQUIREMENT"):
                coordinator.run(mission_id="MISSION-BAD-1", objective="A booking app")
            with self.assertRaises(KeyError):
                catalog.latest_artifact("MISSION-BAD-1", "design-bundle")

    def test_revision_disabled_reports_exhausted_blocker(self):
        worker = RevisingArchitectureWorker()
        coordinator = DesignPodCoordinator(
            product_worker=ProductWorker(),
            architecture_worker=worker,
            ux_worker=UXWorkerImpl(),
            max_revision_rounds=0,
        )
        with self.assertRaisesRegex(RuntimeError, "design_revision_exhausted:ARCHITECTURE_UNKNOWN_REQUIREMENT"):
            coordinator.run(mission_id="MISSION-NOREV", objective="A booking app")
        self.assertEqual(worker.revision_requests, [])

    def test_invalid_intake_is_rejected_before_workers(self):
        coordinator = DesignPodCoordinator(
            product_worker=ProductWorker(), architecture_worker=ArchitectureWorker(), ux_worker=UXWorkerImpl()
        )
        with self.assertRaises(ValueError):
            coordinator.run(mission_id="", objective="")


if __name__ == "__main__":
    unittest.main()
