from __future__ import annotations

from .contracts import (
    AttemptRecord,
    CompensationPlan,
    CompensationRecord,
    DeadlineObservation,
    OperationSpec,
    RecoveryDecision,
    ReliabilityMetric,
)
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
        current_circuit = self.store.load_circuit(attempt.operation_id)
        if current_circuit.state == "OPEN":
            raise RuntimeError("circuit is OPEN; probe transition required before a new attempt")
        decision = self.engine.decide(operation=operation, attempt=attempt, circuit=current_circuit)
        next_circuit = self.engine.next_circuit_state(current=current_circuit, attempt=attempt)
        if next_circuit.state == "OPEN" and decision.action == "RETRY":
            decision = RecoveryDecision(
                operation_id=operation.operation_id,
                action="STOP",
                reason="circuit_opened_after_failure_threshold",
            )
            decision.validate()
        self.store.append_attempt_and_decision(
            attempt=attempt,
            decision=decision,
            circuit=next_circuit,
        )
        self.store.append_metric(
            ReliabilityMetric(
                mission_id=operation.mission_id,
                operation_id=operation.operation_id,
                name="attempt_total",
                value=1.0,
            )
        )
        if attempt.outcome != "SUCCESS":
            self.store.append_metric(
                ReliabilityMetric(
                    mission_id=operation.mission_id,
                    operation_id=operation.operation_id,
                    name="attempt_failure_total",
                    value=1.0,
                )
            )
        return decision

    def record_deadline(self, *, operation_id: str, attempt: int, elapsed_seconds: float) -> DeadlineObservation:
        operation = self.store.load_operation(operation_id)
        result = "TIMED_OUT" if elapsed_seconds >= operation.timeout_seconds else "WITHIN_DEADLINE"
        observation = DeadlineObservation(
            operation_id=operation_id,
            attempt=attempt,
            elapsed_seconds=elapsed_seconds,
            timeout_seconds=operation.timeout_seconds,
            result=result,
        )
        observation.validate()
        self.store.append_deadline(observation)
        self.store.append_metric(
            ReliabilityMetric(
                mission_id=operation.mission_id,
                operation_id=operation_id,
                name="timeout_total" if result == "TIMED_OUT" else "within_deadline_total",
                value=1.0,
            )
        )
        return observation

    def open_probe(self, operation_id: str) -> None:
        current = self.store.load_circuit(operation_id)
        half_open = self.engine.half_open(current)
        self.store.save_circuit(operation_id, half_open)

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
        self.store.append_metric(
            ReliabilityMetric(
                mission_id=operation.mission_id,
                operation_id=operation_id,
                name="reconciliation_total",
                value=1.0,
            )
        )
        return decision

    def register_compensation(self, plan: CompensationPlan) -> None:
        operation = self.store.load_operation(plan.operation_id)
        if operation.compensation_ref is None:
            raise ValueError("operation does not declare compensation")
        self.store.register_compensation(plan)

    def record_compensation(self, record: CompensationRecord) -> None:
        operation = self.store.load_operation(record.operation_id)
        self.store.record_compensation(record)
        self.store.append_metric(
            ReliabilityMetric(
                mission_id=operation.mission_id,
                operation_id=record.operation_id,
                name="compensation_success_total" if record.status == "SUCCEEDED" else "compensation_event_total",
                value=1.0,
            )
        )

    def resume_action(self, operation_id: str) -> RecoveryDecision | None:
        state = self.store.state(operation_id)
        status = str(state["status"])
        if status == "READY":
            return None
        return self.store.latest_decision(operation_id)
