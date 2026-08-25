from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TRUST_LEVELS = frozenset({"UNTRUSTED_EXTERNAL", "VALIDATED_EXTERNAL"})
REQUEST_KINDS = frozenset({"TOOL_CALL", "AGENT_TASK"})
RESULT_STATUSES = frozenset({"SUCCEEDED", "FAILED", "INPUT_REQUIRED", "UNKNOWN"})


@dataclass(frozen=True)
class ExternalProvenance:
    protocol: str
    protocol_version: str
    endpoint_id: str
    trust_level: str = "UNTRUSTED_EXTERNAL"

    def validate(self) -> None:
        if not self.protocol.strip() or not self.protocol_version.strip() or not self.endpoint_id.strip():
            raise ValueError("protocol, protocol_version and endpoint_id are required")
        if self.trust_level not in TRUST_LEVELS:
            raise ValueError(f"unknown trust level:{self.trust_level}")


@dataclass(frozen=True)
class ExternalCapability:
    capability_id: str
    name: str
    effect_class: str
    required_factory_capability: str
    provenance: ExternalProvenance

    def validate(self) -> None:
        if not self.capability_id.strip() or not self.name.strip() or not self.required_factory_capability.strip():
            raise ValueError("capability identity and required_factory_capability are required")
        if self.effect_class not in {"READ_ONLY", "LOCAL_WRITE", "EXTERNAL_WRITE"}:
            raise ValueError(f"unknown effect_class:{self.effect_class}")
        self.provenance.validate()


@dataclass(frozen=True)
class ExternalTaskRequest:
    request_id: str
    correlation_id: str
    mission_id: str
    kind: str
    capability_id: str
    payload: dict[str, Any]
    idempotency_key: str | None
    provenance: ExternalProvenance

    def validate(self) -> None:
        if not all(value.strip() for value in (self.request_id, self.correlation_id, self.mission_id, self.capability_id)):
            raise ValueError("request identity, mission and capability are required")
        if self.kind not in REQUEST_KINDS:
            raise ValueError(f"unknown request kind:{self.kind}")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")
        self.provenance.validate()


@dataclass(frozen=True)
class ExternalResult:
    request_id: str
    correlation_id: str
    status: str
    payload: dict[str, Any]
    provenance: ExternalProvenance

    def validate(self) -> None:
        if not self.request_id.strip() or not self.correlation_id.strip():
            raise ValueError("result request_id and correlation_id are required")
        if self.status not in RESULT_STATUSES:
            raise ValueError(f"unknown result status:{self.status}")
        if not isinstance(self.payload, dict):
            raise ValueError("result payload must be an object")
        self.provenance.validate()


@dataclass(frozen=True)
class CapabilityDecision:
    allowed: bool
    reason: str
    capability_id: str

    def validate(self) -> None:
        if not self.reason.strip() or not self.capability_id.strip():
            raise ValueError("capability decision reason and capability_id are required")
