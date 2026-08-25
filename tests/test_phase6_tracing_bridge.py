import tempfile
import unittest
from pathlib import Path

from factory.reliability import AttemptRecord, DurableOperationController, OperationSpec, SQLiteReliabilityStore
from factory.runtime.tracing import SQLiteTracer


class ReliabilityTracingBridgeTests(unittest.TestCase):
    def test_reliability_events_are_visible_in_shared_runtime_tracing(self):
        with tempfile.TemporaryDirectory() as tmp:
            reliability_path = Path(tmp) / "reliability.db"
            trace_path = Path(tmp) / "trace.db"
            tracer = SQLiteTracer(trace_path)
            controller = DurableOperationController(
                store=SQLiteReliabilityStore(reliability_path),
                trace_sink=tracer,
            )
            controller.register(
                OperationSpec(
                    operation_id="OP-T",
                    mission_id="MISSION-T",
                    effect_class="READ_ONLY",
                    max_attempts=2,
                    timeout_seconds=5,
                )
            )
            controller.record_deadline(operation_id="OP-T", attempt=1, elapsed_seconds=6.0)
            controller.record_attempt(AttemptRecord("OP-T", 1, "RETRYABLE_FAILURE", "HTTP_503"))

            events = tracer.events("MISSION-T")
            names = [event["event_name"] for event in events]
            self.assertEqual(names[0], "reliability.operation_registered")
            self.assertIn("reliability.deadline_observed", names)
            self.assertIn("reliability.attempt_decided", names)
            attempt_event = next(event for event in events if event["event_name"] == "reliability.attempt_decided")
            self.assertEqual(attempt_event["actor_id"], "A11-RELIABILITY")
            self.assertEqual(attempt_event["payload"]["decision"], "RETRY")


if __name__ == "__main__":
    unittest.main()
