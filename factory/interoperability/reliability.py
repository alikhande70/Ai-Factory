from __future__ import annotations

from factory.reliability import AttemptRecord, OperationSpec, ReliabilityDecisionEngine, RecoveryDecision

from .contracts import ExternalCapability, ExternalResult


class InteropReliabilityBridge:
    """Maps external protocol outcomes into Phase 6 reliability semantics."""

    def __init__(self, engine: ReliabilityDecisionEngine | None = None) -> None:
        self.engine = engine or ReliabilityDecisionEngine()

    def attempt_from_result(
        self,
        *,
        operation: OperationSpec,
        capability: ExternalCapability,
        result: ExternalResult,
        attempt_number: int,
        retryable_failure: bool = False,
    ) -> AttemptRecord:
        operation.validate()
        capability.validate()
        result.validate()
        if capability.effect_class != operation.effect_class:
            raise ValueError("external capability effect_class does not match operation")
        if result.status == "INPUT_REQUIRED":
            raise RuntimeError("input-required result is not an execution attempt outcome")
        outcome = {
            "SUCCEEDED": "SUCCESS",
            "FAILED": "RETRYABLE_FAILURE" if retryable_failure else "TERMINAL_FAILURE",
            "UNKNOWN": "UNKNOWN",
        }[result.status]
        attempt = AttemptRecord(
            operation_id=operation.operation_id,
            attempt=attempt_number,
            outcome=outcome,
            error_code="EXTERNAL_PROTOCOL_FAILURE" if result.status == "FAILED" else None,
        )
        attempt.validate()
        return attempt

    def decide(
        self,
        *,
        operation: OperationSpec,
        capability: ExternalCapability,
        result: ExternalResult,
        attempt_number: int,
        retryable_failure: bool = False,
    ) -> RecoveryDecision:
        attempt = self.attempt_from_result(
            operation=operation,
            capability=capability,
            result=result,
            attempt_number=attempt_number,
            retryable_failure=retryable_failure,
        )
        return self.engine.decide(operation=operation, attempt=attempt)
