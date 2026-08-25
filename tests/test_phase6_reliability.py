import unittest

from factory.reliability import (
    AttemptRecord,
    CircuitBreakerState,
    OperationSpec,
    ReliabilityDecisionEngine,
)


class ReliabilityContractTests(unittest.TestCase):
    def setUp(self):
        self.engine = ReliabilityDecisionEngine()

    def external_write(self, *, max_attempts=3):
        return OperationSpec(
            operation_id="OP-DEPLOY",
            mission_id="MISSION-REL",
            effect_class="EXTERNAL_WRITE",
            max_attempts=max_attempts,
            timeout_seconds=30,
            idempotency_key="mission-rel:deploy:v1",
            reconciliation_supported=True,
            compensation_ref="runbook://rollback-deploy",
        )

    def test_external_write_requires_idempotency_and_reconciliation(self):
        with self.assertRaisesRegex(ValueError, "idempotency_key"):
            OperationSpec(
                operation_id="OP-WRITE",
                mission_id="M",
                effect_class="EXTERNAL_WRITE",
                max_attempts=2,
                timeout_seconds=5,
                reconciliation_supported=True,
            ).validate()
        with self.assertRaisesRegex(ValueError, "reconciliation support"):
            OperationSpec(
                operation_id="OP-WRITE",
                mission_id="M",
                effect_class="EXTERNAL_WRITE",
                max_attempts=2,
                timeout_seconds=5,
                idempotency_key="key",
            ).validate()

    def test_unknown_external_write_reconciles_before_retry(self):
        operation = self.external_write()
        decision = self.engine.decide(
            operation=operation,
            attempt=AttemptRecord("OP-DEPLOY", 1, "UNKNOWN"),
        )
        self.assertEqual(decision.action, "RECONCILE")
        self.assertIsNone(decision.next_attempt)

    def test_reconciliation_applied_completes_without_retry(self):
        decision = self.engine.decide(
            operation=self.external_write(),
            attempt=AttemptRecord(
                "OP-DEPLOY", 1, "UNKNOWN", reconciliation_result="APPLIED"
            ),
        )
        self.assertEqual(decision.action, "COMPLETE")

    def test_reconciliation_not_applied_allows_bounded_retry(self):
        decision = self.engine.decide(
            operation=self.external_write(max_attempts=2),
            attempt=AttemptRecord(
                "OP-DEPLOY", 1, "UNKNOWN", reconciliation_result="NOT_APPLIED"
            ),
        )
        self.assertEqual(decision.action, "RETRY")
        self.assertEqual(decision.next_attempt, 2)

    def test_reconciliation_unknown_stops_instead_of_duplicate_action(self):
        decision = self.engine.decide(
            operation=self.external_write(),
            attempt=AttemptRecord(
                "OP-DEPLOY", 1, "UNKNOWN", reconciliation_result="UNKNOWN"
            ),
        )
        self.assertEqual(decision.action, "STOP")

    def test_retry_budget_is_enforced(self):
        decision = self.engine.decide(
            operation=self.external_write(max_attempts=2),
            attempt=AttemptRecord("OP-DEPLOY", 2, "RETRYABLE_FAILURE", "HTTP_503"),
        )
        self.assertEqual(decision.action, "STOP")
        self.assertIn("retry_budget_exhausted", decision.reason)

    def test_read_only_unknown_can_retry_without_side_effect_risk(self):
        operation = OperationSpec(
            operation_id="OP-READ",
            mission_id="MISSION-REL",
            effect_class="READ_ONLY",
            max_attempts=2,
            timeout_seconds=5,
        )
        decision = self.engine.decide(
            operation=operation,
            attempt=AttemptRecord("OP-READ", 1, "UNKNOWN"),
        )
        self.assertEqual(decision.action, "RETRY")

    def test_ambiguous_local_write_does_not_blind_retry(self):
        operation = OperationSpec(
            operation_id="OP-LOCAL",
            mission_id="MISSION-REL",
            effect_class="LOCAL_WRITE",
            max_attempts=3,
            timeout_seconds=5,
        )
        decision = self.engine.decide(
            operation=operation,
            attempt=AttemptRecord("OP-LOCAL", 1, "UNKNOWN"),
        )
        self.assertEqual(decision.action, "STOP")

    def test_circuit_opens_at_threshold_and_blocks_execution(self):
        state = CircuitBreakerState(failure_threshold=2)
        state = self.engine.next_circuit_state(
            current=state,
            attempt=AttemptRecord("OP-DEPLOY", 1, "RETRYABLE_FAILURE"),
        )
        self.assertEqual(state.state, "CLOSED")
        state = self.engine.next_circuit_state(
            current=state,
            attempt=AttemptRecord("OP-DEPLOY", 2, "RETRYABLE_FAILURE"),
        )
        self.assertEqual(state.state, "OPEN")

        decision = self.engine.decide(
            operation=self.external_write(max_attempts=3),
            attempt=AttemptRecord("OP-DEPLOY", 2, "RETRYABLE_FAILURE"),
            circuit=state,
        )
        self.assertEqual(decision.action, "STOP")
        self.assertEqual(decision.reason, "circuit_open")

    def test_success_resets_circuit(self):
        open_state = CircuitBreakerState(
            state="OPEN", consecutive_failures=3, failure_threshold=3
        )
        half_open = self.engine.half_open(open_state)
        self.assertEqual(half_open.state, "HALF_OPEN")
        reset = self.engine.next_circuit_state(
            current=half_open,
            attempt=AttemptRecord("OP-DEPLOY", 1, "SUCCESS"),
        )
        self.assertEqual(reset.state, "CLOSED")
        self.assertEqual(reset.consecutive_failures, 0)


if __name__ == "__main__":
    unittest.main()
