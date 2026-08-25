from __future__ import annotations

from typing import Any

from .contracts import (
    CapabilityDecision,
    ExternalCapability,
    ExternalProvenance,
    ExternalResult,
    ExternalTaskRequest,
)


SUPPORTED_A2A_VERSION = "1.0.0"


class A2AAdapter:
    """Pure A2A boundary translator. Transport bindings stay outside canonical semantics."""

    protocol = "A2A"

    def __init__(self, *, endpoint_id: str, protocol_version: str) -> None:
        if protocol_version != SUPPORTED_A2A_VERSION:
            raise ValueError(f"unsupported A2A version:{protocol_version}")
        if not endpoint_id.strip():
            raise ValueError("endpoint_id is required")
        self.endpoint_id = endpoint_id
        self.protocol_version = protocol_version

    def provenance(self) -> ExternalProvenance:
        return ExternalProvenance(
            protocol=self.protocol,
            protocol_version=self.protocol_version,
            endpoint_id=self.endpoint_id,
        )

    def discover_skill(self, descriptor: dict[str, Any]) -> ExternalCapability:
        skill_id = descriptor.get("id")
        name = descriptor.get("name")
        required_factory_capability = descriptor.get("required_factory_capability")
        effect_class = descriptor.get("effect_class", "READ_ONLY")
        if not isinstance(skill_id, str) or not skill_id.strip():
            raise ValueError("A2A skill id is required")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("A2A skill name is required")
        if not isinstance(required_factory_capability, str) or not required_factory_capability.strip():
            raise ValueError("A2A skill must declare required_factory_capability")
        capability = ExternalCapability(
            capability_id=f"a2a:{self.endpoint_id}:{skill_id}",
            name=name,
            effect_class=str(effect_class),
            required_factory_capability=required_factory_capability,
            provenance=self.provenance(),
        )
        capability.validate()
        return capability

    def authorize_capability(
        self,
        *,
        capability: ExternalCapability,
        factory_capabilities: tuple[str, ...],
    ) -> CapabilityDecision:
        capability.validate()
        if capability.provenance.protocol != self.protocol or capability.provenance.endpoint_id != self.endpoint_id:
            decision = CapabilityDecision(False, "capability_provenance_mismatch", capability.capability_id)
        elif capability.required_factory_capability not in set(factory_capabilities):
            decision = CapabilityDecision(False, "factory_capability_missing", capability.capability_id)
        else:
            decision = CapabilityDecision(True, "capability_intersection_allowed", capability.capability_id)
        decision.validate()
        return decision

    def build_task(
        self,
        *,
        request_id: str,
        correlation_id: str,
        mission_id: str,
        capability: ExternalCapability,
        message: dict[str, Any],
        factory_capabilities: tuple[str, ...],
        idempotency_key: str | None = None,
    ) -> ExternalTaskRequest:
        decision = self.authorize_capability(
            capability=capability,
            factory_capabilities=factory_capabilities,
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)
        if capability.effect_class == "EXTERNAL_WRITE" and (not idempotency_key or not idempotency_key.strip()):
            raise ValueError("external-write A2A task requires idempotency_key")
        request = ExternalTaskRequest(
            request_id=request_id,
            correlation_id=correlation_id,
            mission_id=mission_id,
            kind="AGENT_TASK",
            capability_id=capability.capability_id,
            payload={"skill_name": capability.name, "message": dict(message)},
            idempotency_key=idempotency_key,
            provenance=self.provenance(),
        )
        request.validate()
        return request

    def translate_result(
        self,
        *,
        request: ExternalTaskRequest,
        task_state: str,
        payload: dict[str, Any],
    ) -> ExternalResult:
        status_map = {
            "completed": "SUCCEEDED",
            "failed": "FAILED",
            "input-required": "INPUT_REQUIRED",
            "unknown": "UNKNOWN",
        }
        if task_state not in status_map:
            raise ValueError(f"unsupported A2A task state:{task_state}")
        result = ExternalResult(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status=status_map[task_state],
            payload=dict(payload),
            provenance=self.provenance(),
        )
        result.validate()
        return result
