from __future__ import annotations

from dataclasses import dataclass


EFFECT_CLASSES = frozenset({"READ_ONLY", "LOCAL_WRITE", "EXTERNAL_WRITE"})
ATTEMPT_OUTCOMES = frozenset({"SUCCESS", "RETRYABLE_FAILURE", "TERMINAL_FAILURE", "UNKNOWN"})
RECONCILIATION_RESULTS = frozenset({"APPLIED", "NOT_APPLIED", "UNKNOWN"})
RECOVERY_ACTIONS = frozenset({"COMPLETE", "RETRY", "RECONCILE", "STOP"})
CIRCUIT_STATES = frozenset({"CLOSED", "OPEN", "HALF_OPEN"})
COMPENSATION_STATES = frozenset({"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "NOT_REQUIRED"})
DEADLINE_RESULTS = frozenset({"WITHIN_DEADLINE", "TIMED_OUT"})


@dataclass(frozen=True)
class OperationSpec:
    operation_id: str
    mission_id: str
    effect_class: str
    max_attempts: int
    timeout_seconds: int
    idempotency_key: str | None = None
    reconciliation_supported: bool = False
    compensation_ref: str | None = None

    def validate(self) -> None:
        if not self.operation_id.strip() or not self.mission_id.strip():
            raise ValueError("operation_id and mission_id are required")
        if self.effect_class not in EFFECT_CLASSES:
            raise ValueError(f"unknown effect_class:{self.effect_class}")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1")
        if self.effect_class == "READ_ONLY" and self.compensation_ref is not None:
            raise ValueError("READ_ONLY operation cannot define compensation")
        if self.effect_class == "EXTERNAL_WRITE":
            if not self.idempotency_key or not self.idempotency_key.strip():
                raise ValueError("EXTERNAL_WRITE requires a stable idempotency_key")
            if not self.reconciliation_supported:
                raise ValueError("EXTERNAL_WRITE requires reconciliation support")


@dataclass(frozen=True)
class AttemptRecord:
    operation_id: str
    attempt: int
    outcome: str
    error_code: str | None = None
    reconciliation_result: str | None = None

    def validate(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("operation_id is required")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        if self.outcome not in ATTEMPT_OUTCOMES:
            raise ValueError(f"unknown attempt outcome:{self.outcome}")
        if self.reconciliation_result is not None and self.reconciliation_result not in RECONCILIATION_RESULTS:
            raise ValueError(f"unknown reconciliation result:{self.reconciliation_result}")
        if self.outcome != "UNKNOWN" and self.reconciliation_result is not None:
            raise ValueError("reconciliation_result is only valid for UNKNOWN outcome")


@dataclass(frozen=True)
class CircuitBreakerState:
    state: str = "CLOSED"
    consecutive_failures: int = 0
    failure_threshold: int = 3

    def validate(self) -> None:
        if self.state not in CIRCUIT_STATES:
            raise ValueError(f"unknown circuit state:{self.state}")
        if self.consecutive_failures < 0:
            raise ValueError("consecutive_failures must be >= 0")
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.state == "OPEN" and self.consecutive_failures < self.failure_threshold:
            raise ValueError("OPEN circuit requires threshold failures")


@dataclass(frozen=True)
class RecoveryDecision:
    operation_id: str
    action: str
    reason: str
    next_attempt: int | None = None

    def validate(self) -> None:
        if not self.operation_id.strip() or not self.reason.strip():
            raise ValueError("recovery decision identity and reason are required")
        if self.action not in RECOVERY_ACTIONS:
            raise ValueError(f"unknown recovery action:{self.action}")
        if self.action == "RETRY":
            if self.next_attempt is None or self.next_attempt < 2:
                raise ValueError("RETRY requires next_attempt >= 2")
        elif self.next_attempt is not None:
            raise ValueError("only RETRY may set next_attempt")


@dataclass(frozen=True)
class DeadlineObservation:
    operation_id: str
    attempt: int
    elapsed_seconds: float
    timeout_seconds: int
    result: str

    def validate(self) -> None:
        if not self.operation_id.strip() or self.attempt < 1:
            raise ValueError("deadline observation identity is required")
        if self.elapsed_seconds < 0 or self.timeout_seconds < 1:
            raise ValueError("deadline values must be non-negative and timeout >= 1")
        if self.result not in DEADLINE_RESULTS:
            raise ValueError(f"unknown deadline result:{self.result}")
        expected = "TIMED_OUT" if self.elapsed_seconds >= self.timeout_seconds else "WITHIN_DEADLINE"
        if self.result != expected:
            raise ValueError("deadline result does not match elapsed/timeout values")


@dataclass(frozen=True)
class CompensationPlan:
    operation_id: str
    compensation_ref: str
    reason: str
    requires_human_approval: bool = False

    def validate(self) -> None:
        if not self.operation_id.strip() or not self.compensation_ref.strip() or not self.reason.strip():
            raise ValueError("compensation plan identity, ref and reason are required")


@dataclass(frozen=True)
class CompensationRecord:
    operation_id: str
    status: str
    evidence_ref: str | None = None
    error_code: str | None = None

    def validate(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("operation_id is required")
        if self.status not in COMPENSATION_STATES:
            raise ValueError(f"unknown compensation status:{self.status}")
        if self.status == "SUCCEEDED" and (not self.evidence_ref or not self.evidence_ref.strip()):
            raise ValueError("successful compensation requires evidence_ref")


@dataclass(frozen=True)
class ReliabilityMetric:
    mission_id: str
    name: str
    value: float
    operation_id: str | None = None
    unit: str = "count"

    def validate(self) -> None:
        if not self.mission_id.strip() or not self.name.strip() or not self.unit.strip():
            raise ValueError("metric mission_id, name and unit are required")
        if self.operation_id is not None and not self.operation_id.strip():
            raise ValueError("operation_id cannot be blank")
