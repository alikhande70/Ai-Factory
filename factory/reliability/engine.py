from __future__ import annotations

from .contracts import AttemptRecord, CircuitBreakerState, OperationSpec, RecoveryDecision


class ReliabilityDecisionEngine:
    """Pure decision logic for retry, reconciliation and stop behavior."""

    def decide(
        self,
        *,
        operation: OperationSpec,
        attempt: AttemptRecord,
        circuit: CircuitBreakerState | None = None,
    ) -> RecoveryDecision:
        operation.validate()
        attempt.validate()
        circuit = circuit or CircuitBreakerState()
        circuit.validate()

        if attempt.operation_id != operation.operation_id:
            raise ValueError("attempt/operation identity mismatch")
        if attempt.attempt > operation.max_attempts:
            raise ValueError("attempt exceeds operation max_attempts")

        if circuit.state == "OPEN":
            return self._decision(operation, "STOP", "circuit_open")

        if attempt.outcome == "SUCCESS":
            return self._decision(operation, "COMPLETE", "operation_succeeded")

        if attempt.outcome == "TERMINAL_FAILURE":
            return self._decision(operation, "STOP", "terminal_failure")

        if attempt.outcome == "RETRYABLE_FAILURE":
            return self._retry_or_stop(operation, attempt, reason="retryable_failure")

        # UNKNOWN is deliberately conservative. For a side effect, timeout or lost
        # acknowledgement does not prove failure and must never become blind retry.
        if operation.effect_class == "EXTERNAL_WRITE":
            if attempt.reconciliation_result is None:
                return self._decision(operation, "RECONCILE", "external_write_outcome_unknown")
            if attempt.reconciliation_result == "APPLIED":
                return self._decision(operation, "COMPLETE", "reconciliation_confirmed_applied")
            if attempt.reconciliation_result == "NOT_APPLIED":
                return self._retry_or_stop(operation, attempt, reason="reconciliation_confirmed_not_applied")
            return self._decision(operation, "STOP", "reconciliation_remains_unknown")

        if operation.effect_class == "READ_ONLY":
            return self._retry_or_stop(operation, attempt, reason="read_outcome_unknown")

        # LOCAL_WRITE ambiguity must be resolved by the transactional/canonical
        # state owner instead of assuming the write did or did not happen.
        return self._decision(operation, "STOP", "local_write_outcome_unknown_requires_state_recovery")

    def next_circuit_state(
        self,
        *,
        current: CircuitBreakerState,
        attempt: AttemptRecord,
    ) -> CircuitBreakerState:
        current.validate()
        attempt.validate()

        if attempt.outcome == "SUCCESS":
            state = CircuitBreakerState(
                state="CLOSED",
                consecutive_failures=0,
                failure_threshold=current.failure_threshold,
            )
            state.validate()
            return state

        if attempt.outcome in {"RETRYABLE_FAILURE", "TERMINAL_FAILURE", "UNKNOWN"}:
            failures = current.consecutive_failures + 1
            state = "OPEN" if failures >= current.failure_threshold else "CLOSED"
            updated = CircuitBreakerState(
                state=state,
                consecutive_failures=failures,
                failure_threshold=current.failure_threshold,
            )
            updated.validate()
            return updated

        raise ValueError(f"unsupported attempt outcome:{attempt.outcome}")

    def half_open(self, current: CircuitBreakerState) -> CircuitBreakerState:
        current.validate()
        if current.state != "OPEN":
            raise RuntimeError("only OPEN circuit can enter HALF_OPEN")
        state = CircuitBreakerState(
            state="HALF_OPEN",
            consecutive_failures=current.consecutive_failures,
            failure_threshold=current.failure_threshold,
        )
        state.validate()
        return state

    @staticmethod
    def _decision(operation: OperationSpec, action: str, reason: str) -> RecoveryDecision:
        decision = RecoveryDecision(operation_id=operation.operation_id, action=action, reason=reason)
        decision.validate()
        return decision

    def _retry_or_stop(
        self,
        operation: OperationSpec,
        attempt: AttemptRecord,
        *,
        reason: str,
    ) -> RecoveryDecision:
        if attempt.attempt >= operation.max_attempts:
            return self._decision(operation, "STOP", f"{reason}:retry_budget_exhausted")
        decision = RecoveryDecision(
            operation_id=operation.operation_id,
            action="RETRY",
            reason=reason,
            next_attempt=attempt.attempt + 1,
        )
        decision.validate()
        return decision
