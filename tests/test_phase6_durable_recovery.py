import tempfile
import unittest

from factory.reliability import (
    AttemptRecord,
    DurableOperationController,
    OperationSpec,
    SQLiteReliabilityStore,
)


class DurableReliabilityRecoveryTests(unittest.TestCase):
    def operation(self, *, max_attempts=3):
        return OperationSpec(
            operation_id="OP-EXTERNAL-WRITE",
            mission_id="MISSION-DURABLE",
            effect_class="EXTERNAL_WRITE",
            max_attempts=max_attempts,
            timeout_seconds=20,
            idempotency_key="MISSION-DURABLE:OP-EXTERNAL-WRITE:v1",
            reconciliation_supported=True,
            compensation_ref="runbook://compensate",
        )

    def test_restart_preserves_reconcile_required_and_never_blind_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/reliability.db"
            first = DurableOperationController(store=SQLiteReliabilityStore(path))
            first.register(self.operation())
            decision = first.record_attempt(
                AttemptRecord("OP-EXTERNAL-WRITE", 1, "UNKNOWN", "TIMEOUT")
            )
            self.assertEqual(decision.action, "RECONCILE")

            # Simulate process death/restart by constructing fresh store/controller objects.
            resumed = DurableOperationController(store=SQLiteReliabilityStore(path))
            restored = resumed.resume_action("OP-EXTERNAL-WRITE")
            self.assertIsNotNone(restored)
            self.assertEqual(restored.action, "RECONCILE")
            self.assertEqual(
                resumed.store.state("OP-EXTERNAL-WRITE")["status"],
                "RECONCILE_REQUIRED",
            )

            after_reconcile = resumed.reconcile(
                operation_id="OP-EXTERNAL-WRITE", result="NOT_APPLIED"
            )
            self.assertEqual(after_reconcile.action, "RETRY")
            self.assertEqual(after_reconcile.next_attempt, 2)

            retry_result = resumed.record_attempt(
                AttemptRecord("OP-EXTERNAL-WRITE", 2, "SUCCESS")
            )
            self.assertEqual(retry_result.action, "COMPLETE")
            self.assertEqual(
                resumed.store.state("OP-EXTERNAL-WRITE")["status"], "COMPLETED"
            )

    def test_reconciliation_applied_completes_without_second_external_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteReliabilityStore(f"{directory}/reliability.db")
            controller = DurableOperationController(store=store)
            controller.register(self.operation())
            controller.record_attempt(
                AttemptRecord("OP-EXTERNAL-WRITE", 1, "UNKNOWN", "CONNECTION_LOST")
            )
            decision = controller.reconcile(
                operation_id="OP-EXTERNAL-WRITE", result="APPLIED"
            )
            self.assertEqual(decision.action, "COMPLETE")
            self.assertEqual(store.state("OP-EXTERNAL-WRITE")["latest_attempt"], 1)
            attempt_events = [e for e in store.events("OP-EXTERNAL-WRITE") if e["event_type"] == "ATTEMPT"]
            self.assertEqual(len(attempt_events), 1)

    def test_reconciliation_remaining_unknown_stops_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteReliabilityStore(f"{directory}/reliability.db")
            controller = DurableOperationController(store=store)
            controller.register(self.operation())
            controller.record_attempt(
                AttemptRecord("OP-EXTERNAL-WRITE", 1, "UNKNOWN", "TIMEOUT")
            )
            decision = controller.reconcile(
                operation_id="OP-EXTERNAL-WRITE", result="UNKNOWN"
            )
            self.assertEqual(decision.action, "STOP")
            self.assertEqual(store.state("OP-EXTERNAL-WRITE")["status"], "STOPPED")

    def test_retry_attempt_sequence_is_durable_and_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteReliabilityStore(f"{directory}/reliability.db")
            controller = DurableOperationController(store=store)
            controller.register(self.operation(max_attempts=3))
            first = controller.record_attempt(
                AttemptRecord("OP-EXTERNAL-WRITE", 1, "RETRYABLE_FAILURE", "HTTP_503")
            )
            self.assertEqual(first.action, "RETRY")
            with self.assertRaisesRegex(ValueError, "attempt sequence mismatch"):
                controller.record_attempt(
                    AttemptRecord("OP-EXTERNAL-WRITE", 3, "SUCCESS")
                )
            self.assertEqual(store.state("OP-EXTERNAL-WRITE")["latest_attempt"], 1)

    def test_terminal_operation_rejects_late_duplicate_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteReliabilityStore(f"{directory}/reliability.db")
            controller = DurableOperationController(store=store)
            controller.register(self.operation())
            controller.record_attempt(AttemptRecord("OP-EXTERNAL-WRITE", 1, "SUCCESS"))
            with self.assertRaisesRegex(RuntimeError, "terminal reliability operation"):
                controller.record_attempt(AttemptRecord("OP-EXTERNAL-WRITE", 2, "SUCCESS"))


if __name__ == "__main__":
    unittest.main()
