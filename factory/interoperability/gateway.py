from __future__ import annotations

from typing import Any, Protocol

from .a2a import A2AAdapter
from .contracts import ExternalCapability, ExternalResult
from .mcp import MCPAdapter
from .policy import InteropPolicyGuard
from .transport import InteropTransport


class InteropTraceSink(Protocol):
    def trace(self, *, mission_id: str, actor_id: str, event_name: str, payload: dict[str, Any]) -> int: ...


class BoundedInteroperabilityGateway:
    """Executes bounded adapter/transport flows without granting external authority."""

    def __init__(
        self,
        *,
        policy_guard: InteropPolicyGuard | None = None,
        trace_sink: InteropTraceSink | None = None,
    ) -> None:
        self.policy_guard = policy_guard or InteropPolicyGuard()
        self.trace_sink = trace_sink

    def _trace(self, *, mission_id: str, event_name: str, payload: dict[str, Any]) -> None:
        if self.trace_sink is not None:
            self.trace_sink.trace(
                mission_id=mission_id,
                actor_id="INTEROP-GATEWAY",
                event_name=event_name,
                payload=payload,
            )

    def call_mcp(
        self,
        *,
        adapter: MCPAdapter,
        transport: InteropTransport,
        descriptor: dict[str, Any],
        request_id: str,
        correlation_id: str,
        mission_id: str,
        arguments: dict[str, Any],
        factory_capabilities: tuple[str, ...],
        protected: bool,
        approval_status: str | None,
        budget_available: bool,
        idempotency_key: str | None = None,
    ) -> tuple[ExternalCapability, ExternalResult]:
        capability = adapter.discover_tool(descriptor)
        policy = self.policy_guard.authorize(
            capability=capability,
            factory_capabilities=factory_capabilities,
            protected=protected,
            approval_status=approval_status,
            budget_available=budget_available,
        )
        if not policy.allowed:
            raise PermissionError(policy.reason)
        request = adapter.build_tool_call(
            request_id=request_id,
            correlation_id=correlation_id,
            mission_id=mission_id,
            capability=capability,
            arguments=arguments,
            factory_capabilities=factory_capabilities,
            idempotency_key=idempotency_key,
        )
        self._trace(
            mission_id=mission_id,
            event_name="interop.request_dispatched",
            payload={
                "protocol": "MCP",
                "protocol_version": adapter.protocol_version,
                "endpoint_id": adapter.endpoint_id,
                "transport_id": transport.transport_id,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "capability_id": capability.capability_id,
                "trust_level": request.provenance.trust_level,
            },
        )
        raw = transport.invoke(request)
        result_type = raw.get("result_type")
        payload = raw.get("payload")
        if not isinstance(result_type, str) or not isinstance(payload, dict):
            raise ValueError("malformed MCP transport result")
        result = adapter.translate_result(request=request, result_type=result_type, payload=payload)
        self._trace(
            mission_id=mission_id,
            event_name="interop.result_received",
            payload={
                "protocol": "MCP",
                "request_id": result.request_id,
                "correlation_id": result.correlation_id,
                "status": result.status,
                "trust_level": result.provenance.trust_level,
            },
        )
        return capability, result

    def delegate_a2a(
        self,
        *,
        adapter: A2AAdapter,
        transport: InteropTransport,
        descriptor: dict[str, Any],
        request_id: str,
        correlation_id: str,
        mission_id: str,
        message: dict[str, Any],
        factory_capabilities: tuple[str, ...],
        protected: bool,
        approval_status: str | None,
        budget_available: bool,
        idempotency_key: str | None = None,
    ) -> tuple[ExternalCapability, ExternalResult]:
        capability = adapter.discover_skill(descriptor)
        policy = self.policy_guard.authorize(
            capability=capability,
            factory_capabilities=factory_capabilities,
            protected=protected,
            approval_status=approval_status,
            budget_available=budget_available,
        )
        if not policy.allowed:
            raise PermissionError(policy.reason)
        request = adapter.build_task(
            request_id=request_id,
            correlation_id=correlation_id,
            mission_id=mission_id,
            capability=capability,
            message=message,
            factory_capabilities=factory_capabilities,
            idempotency_key=idempotency_key,
        )
        self._trace(
            mission_id=mission_id,
            event_name="interop.request_dispatched",
            payload={
                "protocol": "A2A",
                "protocol_version": adapter.protocol_version,
                "endpoint_id": adapter.endpoint_id,
                "transport_id": transport.transport_id,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "capability_id": capability.capability_id,
                "trust_level": request.provenance.trust_level,
            },
        )
        raw = transport.invoke(request)
        task_state = raw.get("task_state")
        payload = raw.get("payload")
        if not isinstance(task_state, str) or not isinstance(payload, dict):
            raise ValueError("malformed A2A transport result")
        result = adapter.translate_result(request=request, task_state=task_state, payload=payload)
        self._trace(
            mission_id=mission_id,
            event_name="interop.result_received",
            payload={
                "protocol": "A2A",
                "request_id": result.request_id,
                "correlation_id": result.correlation_id,
                "status": result.status,
                "trust_level": result.provenance.trust_level,
            },
        )
        return capability, result
