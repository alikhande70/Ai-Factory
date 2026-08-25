import tempfile
import unittest
from pathlib import Path

from factory.reliability import (
    AttemptRecord,
    DurableOperationController,
    MissionRecoveryCoordinator,
    OperationSpec,
    ReleasePreviewPlan,
    SQLiteReliabilityStore,
)


class Phase6MissionRecoveryTests(unittest.TestCase):
    def register(self, controller, operation_id):
        controller.register(
            OperationSpec(
                operation_id=operation_id,
                mission_id="MISSION-R",
                effect_class="EXTERNAL_WRITE",
                max_attempts=3,
                timeout_seconds=5,
                idempotency_key=f"MISSION-R:{operation_id}",
                reconciliation_supported=True,
                compensation_ref=f"runbook://rollback/{operation_id}",
            )
        )

    def test_restart_reconstructs_mixed_mission_state_without_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.db"
            controller = DurableOperationController(store=SQLiteReliabilityStore(path))
            self.register(controller, "OP-DONE")
            self.register(controller, "OP-AMBIG")
            self.register(controller, "OP-READY")

            controller.record_attempt(AttemptRecord("OP-DONE", 1, "SUCCESS"))
            controller.record_attempt(AttemptRecord("OP-AMBIG", 1, "UNKNOWN"))

            restarted = SQLiteReliabilityStore(path)
            report = MissionRecoveryCoordinator(restarted).recover(
                mission_id="MISSION-R",
                operation_ids=("OP-DONE", "OP-AMBIG", "OP-READY"),
            )
            actions = {item.operation_id: item.action for item in report.items}
            self.assertEqual(actions["OP-DONE"], "COMPLETE")
            self.assertEqual(actions["OP-AMBIG"], "RECONCILE")
            self.assertEqual(actions["OP-READY"], "READY")
            self.assertFalse(report.safe_to_continue)

    def test_mission_recovery_rejects_cross_mission_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.db"
            controller = DurableOperationController(store=SQLiteReliabilityStore(path))
            self.register(controller, "OP-1")
            controller.register(
                OperationSpec(
                    operation_id="OP-OTHER",
                    mission_id="OTHER",
                    effect_class="READ_ONLY",
                    max_attempts=1,
                    timeout_seconds=2,
                )
            )
            with self.assertRaisesRegex(ValueError, "different mission"):
                MissionRecoveryCoordinator(controller.store).recover(
                    mission_id="MISSION-R",
                    operation_ids=("OP-1", "OP-OTHER"),
                )

    def test_release_preview_requires_exact_reviewed_fingerprint_and_rollback(self):
        good = ReleasePreviewPlan(
            mission_id="MISSION-R",
            candidate_fingerprint="sha256:abc",
            reviewed_fingerprint="sha256:abc",
            assurance_status="PASS",
            rollback_ref="artifact://rollback-plan/1",
        )
        good.validate()
        self.assertTrue(good.may_execute)

        with self.assertRaisesRegex(ValueError, "reviewed fingerprint"):
            ReleasePreviewPlan(
                mission_id="MISSION-R",
                candidate_fingerprint="sha256:new",
                reviewed_fingerprint="sha256:old",
                assurance_status="PASS",
                rollback_ref="artifact://rollback-plan/1",
            ).validate()

    def test_production_release_is_human_gated(self):
        with self.assertRaisesRegex(ValueError, "human approval"):
            ReleasePreviewPlan(
                mission_id="MISSION-R",
                candidate_fingerprint="sha256:abc",
                reviewed_fingerprint="sha256:abc",
                assurance_status="PASS",
                rollback_ref="artifact://rollback-plan/1",
                environment="PRODUCTION",
                human_approval_granted=False,
            ).validate()

        approved = ReleasePreviewPlan(
            mission_id="MISSION-R",
            candidate_fingerprint="sha256:abc",
            reviewed_fingerprint="sha256:abc",
            assurance_status="PASS",
            rollback_ref="artifact://rollback-plan/1",
            environment="PRODUCTION",
            human_approval_granted=True,
        )
        self.assertTrue(approved.may_execute)

    def test_release_rejects_nonpassing_assurance(self):
        with self.assertRaisesRegex(ValueError, "assurance PASS"):
            ReleasePreviewPlan(
                mission_id="MISSION-R",
                candidate_fingerprint="sha256:abc",
                reviewed_fingerprint="sha256:abc",
                assurance_status="CHANGES_REQUIRED",
                rollback_ref="artifact://rollback-plan/1",
            ).validate()


if __name__ == "__main__":
    unittest.main()
