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

    def design_architecture(self, *, mission_id: str, objective: str, product: ProductDesignOutput) -> ArchitectureDesignOutput:
        return ArchitectureDesignOutput(
            decisions=(
                ArchitectureDecision(
                    "ADR-1", "Transactional booking", "Use one transactional application service", "Protect slot consistency", ("REQ-1",)
                ),
            ),
            risks=("database contention",),
        )


class UXWorkerImpl:
    agent_id = "A04-UX"

    def design_ux(self, *, mission_id: str, objective: str, product: ProductDesignOutput) -> UXDesignOutput:
        return UXDesignOutput(
            flows=(UXFlow("UX-1", "Create booking", "user", ("Choose slot", "Confirm", "See result"), ("REQ-1",)),),
            risks=("slot expires during confirmation",),
        )


class InvalidArchitectureWorker(ArchitectureWorker):
    def design_architecture(self, *, mission_id: str, objective: str, product: ProductDesignOutput) -> ArchitectureDesignOutput:
        return ArchitectureDesignOutput(
            decisions=(ArchitectureDecision("ADR-X", "Broken", "None", "Invalid reference", ("REQ-X",)),)
        )


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

    def test_blocking_cross_role_inconsistency_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = SQLiteRuntimeCatalog(f"{directory}/runtime.db")
            coordinator = DesignPodCoordinator(
                product_worker=ProductWorker(),
                architecture_worker=InvalidArchitectureWorker(),
                ux_worker=UXWorkerImpl(),
                catalog=catalog,
            )
            with self.assertRaisesRegex(RuntimeError, "ARCHITECTURE_UNKNOWN_REQUIREMENT"):
                coordinator.run(mission_id="MISSION-BAD-1", objective="A booking app")
            with self.assertRaises(KeyError):
                catalog.latest_artifact("MISSION-BAD-1", "design-bundle")

    def test_invalid_intake_is_rejected_before_workers(self):
        coordinator = DesignPodCoordinator(
            product_worker=ProductWorker(), architecture_worker=ArchitectureWorker(), ux_worker=UXWorkerImpl()
        )
        with self.assertRaises(ValueError):
            coordinator.run(mission_id="", objective="")


if __name__ == "__main__":
    unittest.main()
