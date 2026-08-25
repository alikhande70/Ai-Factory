from __future__ import annotations

from .contracts import AttemptRecord, OperationSpec, RecoveryDecision
from .engine import ReliabilityDecisionEngine
from .store import SQLiteReliabilityStore


class DurableOperationController:
    """Coordinates pure reliability decisions with durable state persistence."""

    def __init__(
        self,
        *,
        store: SQLiteReliabilityStore,
        engine: ReliabilityDecisionEngine | None = None,
    ) -> None:
        self.store = store
        self.engine = engine or ReliabilityDecisionEngine()

    def register(self, operation: OperationSpec) -> None:
        self.store.register(operation)

    def record_attempt(self, attempt: AttemptRecord) -> RecoveryDecision:
        operation = self.store.load_operation(attempt.operation_id)
        decision = self.engine.decide(operation=operation, attempt=attempt)
        self.store.append_attempt_and_decision(attempt=attempt, decision=decision)
        return decision

    def reconcile(self, *, operation_id: str, result: str) -> RecoveryDecision:
        operation = self.store.load_operation(operation_id)
        state = self.store.state(operation_id)
        if state["status"] != "RECONCILE_REQUIRED":
            raise RuntimeError("operation is not waiting for reconciliation")
        previous = self.store.latest_attempt(operation_id)
        if previous.outcome != "UNKNOWN":
            raise RuntimeError("latest attempt is not ambiguous")
        reconciled_attempt = AttemptRecord(
            operation_id=previous.operation_id,
            attempt=previous.attempt,
            outcome="UNKNOWN",
            error_code=previous.error_code,
            reconciliation_result=result,
        )
        decision = self.engine.decide(operation=operation, attempt=reconciled_attempt)
        self.store.append_reconciliation_and_decision(
            operation_id=operation_id,
            reconciliation_result=result,
            decision=decision,
        )
        return decision

    def resume_action(self, operation_id: str) -> RecoveryDecision | None:
        state = self.store.state(operation_id)
        status = str(state["status"])
        if status == "READY":
            return None
        return self.store.latest_decision(operation_id)
