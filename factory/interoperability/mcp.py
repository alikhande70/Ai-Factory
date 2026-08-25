from __future__ import annotations

from typing import Any

from .contracts import (
    CapabilityDecision,
    ExternalCapability,
    ExternalProvenance,
    ExternalResult,
    ExternalTaskRequest,
)


SUPPORTED_MCP_VERSION = "2026-07-28"


class MCPAdapter:
    """Pure boundary translator for MCP. It does not perform transport I/O."""

    protocol = "MCP"

    def __init__(self, *, endpoint_id: str, protocol_version: str) -> None:
        if protocol_version != SUPPORTED_MCP_VERSION:
            raise ValueError(f"unsupported MCP version:{protocol_version}")
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

    def discover_tool(self, descriptor: dict[str, Any]) -> ExternalCapability:
        name = descriptor.get("name")
        effect_class = descriptor.get("effect_class", "READ_ONLY")
        required_factory_capability = descriptor.get("required_factory_capability")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("MCP tool name is required")
        if not isinstance(required_factory_capability, str) or not required_factory_capability.strip():
            raise ValueError("MCP tool must declare required_factory_capability")
        capability = ExternalCapability(
            capability_id=f"mcp:{self.endpoint_id}:{name}",
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

    def build_tool_call(
        self,
        *,
        request_id: str,
        correlation_id: str,
        mission_id: str,
        capability: ExternalCapability,
        arguments: dict[str, Any],
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
            raise ValueError("external-write MCP tool call requires idempotency_key")
        request = ExternalTaskRequest(
            request_id=request_id,
            correlation_id=correlation_id,
            mission_id=mission_id,
            kind="TOOL_CALL",
            capability_id=capability.capability_id,
            payload={"tool_name": capability.name, "arguments": dict(arguments)},
            idempotency_key=idempotency_key,
            provenance=self.provenance(),
        )
        request.validate()
        return request

    def translate_result(
        self,
        *,
        request: ExternalTaskRequest,
        result_type: str,
        payload: dict[str, Any],
    ) -> ExternalResult:
        status_map = {
            "success": "SUCCEEDED",
            "error": "FAILED",
            "input_required": "INPUT_REQUIRED",
            "unknown": "UNKNOWN",
        }
        if result_type not in status_map:
            raise ValueError(f"unsupported MCP result_type:{result_type}")
        result = ExternalResult(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status=status_map[result_type],
            payload=dict(payload),
            provenance=self.provenance(),
        )
        result.validate()
        return result
