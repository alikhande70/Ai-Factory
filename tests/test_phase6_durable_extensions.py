import tempfile
import unittest
from pathlib import Path

from factory.reliability import (
    AttemptRecord,
    CompensationPlan,
    CompensationRecord,
    DurableOperationController,
    OperationSpec,
    SQLiteReliabilityStore,
)


class DurableReliabilityExtensionTests(unittest.TestCase):
    def make_controller(self, path: Path, *, max_attempts: int = 5) -> DurableOperationController:
        store = SQLiteReliabilityStore(path)
        controller = DurableOperationController(store=store)
        controller.register(
            OperationSpec(
                operation_id="OP-1",
                mission_id="MISSION-1",
                effect_class="EXTERNAL_WRITE",
                max_attempts=max_attempts,
                timeout_seconds=10,
                idempotency_key="mission-1:op-1:v1",
                reconciliation_supported=True,
                compensation_ref="runbook://rollback/op-1",
            )
        )
        return controller

    def test_circuit_state_survives_restart_and_requires_explicit_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reliability.db"
            controller = self.make_controller(path)
            controller.record_attempt(AttemptRecord("OP-1", 1, "RETRYABLE_FAILURE"))
            controller.record_attempt(AttemptRecord("OP-1", 2, "RETRYABLE_FAILURE"))
            decision = controller.record_attempt(AttemptRecord("OP-1", 3, "RETRYABLE_FAILURE"))
            self.assertEqual(decision.action, "STOP")
            self.assertEqual(controller.store.load_circuit("OP-1").state, "OPEN")

            restarted = DurableOperationController(store=SQLiteReliabilityStore(path))
            self.assertEqual(restarted.store.load_circuit("OP-1").state, "OPEN")
            with self.assertRaisesRegex(RuntimeError, "OPEN"):
                restarted.record_attempt(AttemptRecord("OP-1", 4, "SUCCESS"))

            restarted.open_probe("OP-1")
            self.assertEqual(restarted.store.load_circuit("OP-1").state, "HALF_OPEN")

    def test_deadline_observation_is_derived_and_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reliability.db"
            controller = self.make_controller(path)
            observation = controller.record_deadline(operation_id="OP-1", attempt=1, elapsed_seconds=10.5)
            self.assertEqual(observation.result, "TIMED_OUT")

            restarted = SQLiteReliabilityStore(path)
            persisted = restarted.latest_deadline("OP-1")
            self.assertEqual(persisted.result, "TIMED_OUT")
            self.assertEqual(persisted.timeout_seconds, 10)

    def test_compensation_requires_declared_plan_and_success_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reliability.db"
            controller = self.make_controller(path)
            plan = CompensationPlan(
                operation_id="OP-1",
                compensation_ref="runbook://rollback/op-1",
                reason="deployment health check failed",
            )
            controller.register_compensation(plan)
            with self.assertRaisesRegex(ValueError, "evidence_ref"):
                controller.record_compensation(CompensationRecord(operation_id="OP-1", status="SUCCEEDED"))

            controller.record_compensation(
                CompensationRecord(
                    operation_id="OP-1",
                    status="SUCCEEDED",
                    evidence_ref="artifact://rollback-proof/1",
                )
            )
            restarted = SQLiteReliabilityStore(path)
            record = restarted.compensation_record("OP-1")
            self.assertIsNotNone(record)
            self.assertEqual(record.status, "SUCCEEDED")

    def test_compensation_plan_must_match_operation_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reliability.db"
            controller = self.make_controller(path)
            with self.assertRaisesRegex(ValueError, "does not match"):
                controller.register_compensation(
                    CompensationPlan(
                        operation_id="OP-1",
                        compensation_ref="runbook://wrong",
                        reason="wrong plan",
                    )
                )

    def test_reliability_metrics_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reliability.db"
            controller = self.make_controller(path)
            controller.record_deadline(operation_id="OP-1", attempt=1, elapsed_seconds=2.0)
            controller.record_attempt(AttemptRecord("OP-1", 1, "RETRYABLE_FAILURE"))

            restarted = SQLiteReliabilityStore(path)
            names = [metric.name for metric in restarted.metrics("MISSION-1")]
            self.assertIn("within_deadline_total", names)
            self.assertIn("attempt_total", names)
            self.assertIn("attempt_failure_total", names)

    def test_attempt_decision_and_circuit_event_are_committed_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reliability.db"
            controller = self.make_controller(path)
            controller.record_attempt(AttemptRecord("OP-1", 1, "RETRYABLE_FAILURE"))
            event_types = [event["event_type"] for event in controller.store.events("OP-1")]
            self.assertEqual(event_types[-3:], ["ATTEMPT", "DECISION", "CIRCUIT"])


if __name__ == "__main__":
    unittest.main()
