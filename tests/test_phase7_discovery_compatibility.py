import unittest

from factory.interoperability import (
    A2AAdapter,
    BoundedInteroperabilityGateway,
    InMemoryInteropTransport,
    MCPAdapter,
)


class Phase7DiscoveryCompatibilityTests(unittest.TestCase):
    def test_mcp_discovery_runs_through_transport_and_produces_canonical_capability(self):
        transport = InMemoryInteropTransport(
            transport_id="fixture-mcp",
            descriptors=(
                {
                    "name": "repo.read",
                    "effect_class": "READ_ONLY",
                    "required_factory_capability": "repo:read",
                },
            ),
            results_by_capability={},
        )
        capabilities = BoundedInteroperabilityGateway().discover_mcp(
            adapter=MCPAdapter(endpoint_id="mcp-local", protocol_version="2026-07-28"),
            transport=transport,
        )
        self.assertEqual(len(capabilities), 1)
        capability = capabilities[0]
        self.assertEqual(capability.name, "repo.read")
        self.assertEqual(capability.effect_class, "READ_ONLY")
        self.assertEqual(capability.required_factory_capability, "repo:read")
        self.assertEqual(capability.provenance.trust_level, "UNTRUSTED_EXTERNAL")

    def test_a2a_discovery_runs_through_transport_and_produces_same_internal_contract(self):
        transport = InMemoryInteropTransport(
            transport_id="fixture-a2a",
            descriptors=(
                {
                    "id": "analyze",
                    "name": "Analyze",
                    "effect_class": "READ_ONLY",
                    "required_factory_capability": "analysis:delegate",
                },
            ),
            results_by_capability={},
        )
        capabilities = BoundedInteroperabilityGateway().discover_a2a(
            adapter=A2AAdapter(endpoint_id="agent-local", protocol_version="1.0.0"),
            transport=transport,
        )
        self.assertEqual(len(capabilities), 1)
        capability = capabilities[0]
        self.assertEqual(capability.name, "Analyze")
        self.assertEqual(capability.effect_class, "READ_ONLY")
        self.assertEqual(capability.required_factory_capability, "analysis:delegate")
        self.assertEqual(capability.provenance.trust_level, "UNTRUSTED_EXTERNAL")

    def test_protocol_replacement_does_not_change_canonical_capability_shape(self):
        mcp = BoundedInteroperabilityGateway().discover_mcp(
            adapter=MCPAdapter(endpoint_id="mcp-local", protocol_version="2026-07-28"),
            transport=InMemoryInteropTransport(
                transport_id="mcp",
                descriptors=(
                    {
                        "name": "Analyze",
                        "effect_class": "READ_ONLY",
                        "required_factory_capability": "analysis:delegate",
                    },
                ),
                results_by_capability={},
            ),
        )[0]
        a2a = BoundedInteroperabilityGateway().discover_a2a(
            adapter=A2AAdapter(endpoint_id="agent-local", protocol_version="1.0.0"),
            transport=InMemoryInteropTransport(
                transport_id="a2a",
                descriptors=(
                    {
                        "id": "analyze",
                        "name": "Analyze",
                        "effect_class": "READ_ONLY",
                        "required_factory_capability": "analysis:delegate",
                    },
                ),
                results_by_capability={},
            ),
        )[0]
        self.assertEqual(mcp.name, a2a.name)
        self.assertEqual(mcp.effect_class, a2a.effect_class)
        self.assertEqual(mcp.required_factory_capability, a2a.required_factory_capability)
        self.assertEqual(type(mcp), type(a2a))

    def test_duplicate_discovered_capability_ids_are_rejected(self):
        transport = InMemoryInteropTransport(
            transport_id="fixture-mcp",
            descriptors=(
                {
                    "name": "repo.read",
                    "effect_class": "READ_ONLY",
                    "required_factory_capability": "repo:read",
                },
                {
                    "name": "repo.read",
                    "effect_class": "READ_ONLY",
                    "required_factory_capability": "repo:read",
                },
            ),
            results_by_capability={},
        )
        with self.assertRaisesRegex(ValueError, "duplicate external capability"):
            BoundedInteroperabilityGateway().discover_mcp(
                adapter=MCPAdapter(endpoint_id="mcp-local", protocol_version="2026-07-28"),
                transport=transport,
            )

    def test_malformed_discovery_descriptor_is_rejected(self):
        transport = InMemoryInteropTransport(
            transport_id="fixture-a2a",
            descriptors=({"id": "missing-name"},),
            results_by_capability={},
        )
        with self.assertRaisesRegex(ValueError, "skill name"):
            BoundedInteroperabilityGateway().discover_a2a(
                adapter=A2AAdapter(endpoint_id="agent-local", protocol_version="1.0.0"),
                transport=transport,
            )


if __name__ == "__main__":
    unittest.main()
