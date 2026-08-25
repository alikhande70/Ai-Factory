import tempfile
import unittest
from pathlib import Path

from factory.interoperability import (
    A2AAdapter,
    BoundedInteroperabilityGateway,
    InMemoryInteropTransport,
    MCPAdapter,
)
from factory.runtime.tracing import SQLiteTracer


class Phase7GatewayTests(unittest.TestCase):
    def test_mcp_gateway_runs_policy_transport_translation_and_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = SQLiteTracer(Path(tmp) / "trace.db")
            adapter = MCPAdapter(endpoint_id="mcp-local", protocol_version="2026-07-28")
            capability_id = "mcp:mcp-local:repo.read"
            transport = InMemoryInteropTransport(
                transport_id="fixture-mcp",
                descriptors=(),
                results_by_capability={
                    capability_id: {"result_type": "success", "payload": {"text": "ok"}}
                },
            )
            gateway = BoundedInteroperabilityGateway(trace_sink=tracer)
            capability, result = gateway.call_mcp(
                adapter=adapter,
                transport=transport,
                descriptor={
                    "name": "repo.read",
                    "effect_class": "READ_ONLY",
                    "required_factory_capability": "repo:read",
                },
                request_id="REQ-1",
                correlation_id="CORR-1",
                mission_id="M-1",
                arguments={"path": "README.md"},
                factory_capabilities=("repo:read",),
                protected=False,
                approval_status=None,
                budget_available=True,
            )
            self.assertEqual(capability.capability_id, capability_id)
            self.assertEqual(result.status, "SUCCEEDED")
            self.assertEqual(result.provenance.trust_level, "UNTRUSTED_EXTERNAL")
            names = [event["event_name"] for event in tracer.events("M-1")]
            self.assertEqual(names, ["interop.request_dispatched", "interop.result_received"])

    def test_gateway_blocks_protected_call_before_transport_without_approval(self):
        adapter = MCPAdapter(endpoint_id="mcp-local", protocol_version="2026-07-28")
        capability_id = "mcp:mcp-local:deploy"
        transport = InMemoryInteropTransport(
            transport_id="fixture-mcp",
            descriptors=(),
            results_by_capability={capability_id: {"result_type": "success", "payload": {}}},
        )
        gateway = BoundedInteroperabilityGateway()
        with self.assertRaisesRegex(PermissionError, "human_approval_required"):
            gateway.call_mcp(
                adapter=adapter,
                transport=transport,
                descriptor={
                    "name": "deploy",
                    "effect_class": "EXTERNAL_WRITE",
                    "required_factory_capability": "deploy:production",
                },
                request_id="REQ-P",
                correlation_id="CORR-P",
                mission_id="M-1",
                arguments={},
                factory_capabilities=("deploy:production",),
                protected=True,
                approval_status=None,
                budget_available=True,
                idempotency_key="M-1:deploy:1",
            )

    def test_malformed_mcp_transport_result_is_rejected(self):
        adapter = MCPAdapter(endpoint_id="mcp-local", protocol_version="2026-07-28")
        capability_id = "mcp:mcp-local:repo.read"
        transport = InMemoryInteropTransport(
            transport_id="fixture-mcp",
            descriptors=(),
            results_by_capability={capability_id: {"payload": {"text": "missing result type"}}},
        )
        with self.assertRaisesRegex(ValueError, "malformed MCP"):
            BoundedInteroperabilityGateway().call_mcp(
                adapter=adapter,
                transport=transport,
                descriptor={
                    "name": "repo.read",
                    "effect_class": "READ_ONLY",
                    "required_factory_capability": "repo:read",
                },
                request_id="REQ-M",
                correlation_id="CORR-M",
                mission_id="M-1",
                arguments={},
                factory_capabilities=("repo:read",),
                protected=False,
                approval_status=None,
                budget_available=True,
            )

    def test_a2a_gateway_delegates_without_promoting_result_to_trusted(self):
        adapter = A2AAdapter(endpoint_id="agent-local", protocol_version="1.0.0")
        capability_id = "a2a:agent-local:analyze"
        transport = InMemoryInteropTransport(
            transport_id="fixture-a2a",
            descriptors=(),
            results_by_capability={
                capability_id: {"task_state": "completed", "payload": {"answer": "candidate"}}
            },
        )
        capability, result = BoundedInteroperabilityGateway().delegate_a2a(
            adapter=adapter,
            transport=transport,
            descriptor={
                "id": "analyze",
                "name": "Analyze",
                "effect_class": "READ_ONLY",
                "required_factory_capability": "analysis:delegate",
            },
            request_id="REQ-A",
            correlation_id="CORR-A",
            mission_id="M-1",
            message={"text": "analyze"},
            factory_capabilities=("analysis:delegate",),
            protected=False,
            approval_status=None,
            budget_available=True,
        )
        self.assertEqual(capability.capability_id, capability_id)
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.provenance.trust_level, "UNTRUSTED_EXTERNAL")

    def test_malformed_a2a_transport_result_is_rejected(self):
        adapter = A2AAdapter(endpoint_id="agent-local", protocol_version="1.0.0")
        capability_id = "a2a:agent-local:analyze"
        transport = InMemoryInteropTransport(
            transport_id="fixture-a2a",
            descriptors=(),
            results_by_capability={capability_id: {"task_state": "completed", "payload": "not-an-object"}},
        )
        with self.assertRaisesRegex(ValueError, "malformed A2A"):
            BoundedInteroperabilityGateway().delegate_a2a(
                adapter=adapter,
                transport=transport,
                descriptor={
                    "id": "analyze",
                    "name": "Analyze",
                    "effect_class": "READ_ONLY",
                    "required_factory_capability": "analysis:delegate",
                },
                request_id="REQ-A",
                correlation_id="CORR-A",
                mission_id="M-1",
                message={},
                factory_capabilities=("analysis:delegate",),
                protected=False,
                approval_status=None,
                budget_available=True,
            )


if __name__ == "__main__":
    unittest.main()
