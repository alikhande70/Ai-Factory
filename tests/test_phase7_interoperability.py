import unittest

from factory.interoperability import (
    A2AAdapter,
    MCPAdapter,
    ExternalCapability,
    ExternalProvenance,
)


class Phase7InteroperabilityTests(unittest.TestCase):
    def test_protocol_versions_are_explicitly_pinned(self):
        with self.assertRaisesRegex(ValueError, "unsupported MCP version"):
            MCPAdapter(endpoint_id="mcp-1", protocol_version="2025-03-26")
        with self.assertRaisesRegex(ValueError, "unsupported A2A version"):
            A2AAdapter(endpoint_id="agent-1", protocol_version="0.3.0")

    def test_mcp_capability_requires_factory_capability_intersection(self):
        adapter = MCPAdapter(endpoint_id="mcp-1", protocol_version="2026-07-28")
        tool = adapter.discover_tool(
            {
                "name": "repo.read",
                "effect_class": "READ_ONLY",
                "required_factory_capability": "repo:read",
            }
        )
        denied = adapter.authorize_capability(capability=tool, factory_capabilities=("artifact:read",))
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "factory_capability_missing")

        allowed = adapter.authorize_capability(capability=tool, factory_capabilities=("repo:read",))
        self.assertTrue(allowed.allowed)

    def test_external_capability_cannot_spoof_endpoint_provenance(self):
        adapter = MCPAdapter(endpoint_id="trusted-endpoint", protocol_version="2026-07-28")
        spoofed = ExternalCapability(
            capability_id="mcp:evil:repo.read",
            name="repo.read",
            effect_class="READ_ONLY",
            required_factory_capability="repo:read",
            provenance=ExternalProvenance(
                protocol="MCP",
                protocol_version="2026-07-28",
                endpoint_id="evil",
            ),
        )
        decision = adapter.authorize_capability(
            capability=spoofed,
            factory_capabilities=("repo:read",),
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "capability_provenance_mismatch")

    def test_external_write_mcp_requires_idempotency_key(self):
        adapter = MCPAdapter(endpoint_id="mcp-1", protocol_version="2026-07-28")
        tool = adapter.discover_tool(
            {
                "name": "repo.write",
                "effect_class": "EXTERNAL_WRITE",
                "required_factory_capability": "repo:write",
            }
        )
        with self.assertRaisesRegex(ValueError, "idempotency_key"):
            adapter.build_tool_call(
                request_id="REQ-1",
                correlation_id="CORR-1",
                mission_id="M-1",
                capability=tool,
                arguments={"path": "README.md"},
                factory_capabilities=("repo:write",),
            )

    def test_mcp_result_preserves_correlation_and_untrusted_provenance(self):
        adapter = MCPAdapter(endpoint_id="mcp-1", protocol_version="2026-07-28")
        tool = adapter.discover_tool(
            {
                "name": "repo.read",
                "effect_class": "READ_ONLY",
                "required_factory_capability": "repo:read",
            }
        )
        request = adapter.build_tool_call(
            request_id="REQ-1",
            correlation_id="CORR-1",
            mission_id="M-1",
            capability=tool,
            arguments={"path": "README.md"},
            factory_capabilities=("repo:read",),
        )
        result = adapter.translate_result(request=request, result_type="success", payload={"text": "data"})
        self.assertEqual(result.request_id, request.request_id)
        self.assertEqual(result.correlation_id, "CORR-1")
        self.assertEqual(result.provenance.trust_level, "UNTRUSTED_EXTERNAL")

    def test_mcp_input_required_maps_without_becoming_approval(self):
        adapter = MCPAdapter(endpoint_id="mcp-1", protocol_version="2026-07-28")
        tool = adapter.discover_tool(
            {
                "name": "needs.input",
                "effect_class": "READ_ONLY",
                "required_factory_capability": "tool:read",
            }
        )
        request = adapter.build_tool_call(
            request_id="REQ-2",
            correlation_id="CORR-2",
            mission_id="M-1",
            capability=tool,
            arguments={},
            factory_capabilities=("tool:read",),
        )
        result = adapter.translate_result(
            request=request,
            result_type="input_required",
            payload={"requests": [{"type": "confirmation"}]},
        )
        self.assertEqual(result.status, "INPUT_REQUIRED")
        self.assertEqual(result.provenance.trust_level, "UNTRUSTED_EXTERNAL")

    def test_a2a_skill_cannot_expand_factory_permissions(self):
        adapter = A2AAdapter(endpoint_id="agent-1", protocol_version="1.0.0")
        skill = adapter.discover_skill(
            {
                "id": "deploy",
                "name": "Deploy",
                "effect_class": "EXTERNAL_WRITE",
                "required_factory_capability": "deploy:production",
            }
        )
        with self.assertRaisesRegex(PermissionError, "factory_capability_missing"):
            adapter.build_task(
                request_id="REQ-A",
                correlation_id="CORR-A",
                mission_id="M-1",
                capability=skill,
                message={"text": "deploy"},
                factory_capabilities=("deploy:preview",),
                idempotency_key="M-1:deploy:1",
            )

    def test_a2a_external_write_requires_idempotency_key(self):
        adapter = A2AAdapter(endpoint_id="agent-1", protocol_version="1.0.0")
        skill = adapter.discover_skill(
            {
                "id": "write",
                "name": "Write",
                "effect_class": "EXTERNAL_WRITE",
                "required_factory_capability": "external:write",
            }
        )
        with self.assertRaisesRegex(ValueError, "idempotency_key"):
            adapter.build_task(
                request_id="REQ-A",
                correlation_id="CORR-A",
                mission_id="M-1",
                capability=skill,
                message={"text": "write"},
                factory_capabilities=("external:write",),
            )

    def test_a2a_result_maps_task_state_without_canonical_trust_promotion(self):
        adapter = A2AAdapter(endpoint_id="agent-1", protocol_version="1.0.0")
        skill = adapter.discover_skill(
            {
                "id": "analysis",
                "name": "Analyze",
                "effect_class": "READ_ONLY",
                "required_factory_capability": "analysis:delegate",
            }
        )
        request = adapter.build_task(
            request_id="REQ-A",
            correlation_id="CORR-A",
            mission_id="M-1",
            capability=skill,
            message={"text": "analyze"},
            factory_capabilities=("analysis:delegate",),
        )
        result = adapter.translate_result(
            request=request,
            task_state="completed",
            payload={"artifact": "candidate-output"},
        )
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.provenance.trust_level, "UNTRUSTED_EXTERNAL")


if __name__ == "__main__":
    unittest.main()
