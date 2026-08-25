"""Protocol-neutral interoperability boundary for external tools and agents."""

from .a2a import A2AAdapter, SUPPORTED_A2A_VERSION
from .contracts import (
    CapabilityDecision,
    ExternalCapability,
    ExternalProvenance,
    ExternalResult,
    ExternalTaskRequest,
)
from .gateway import BoundedInteroperabilityGateway
from .mcp import MCPAdapter, SUPPORTED_MCP_VERSION
from .policy import InteropPolicyDecision, InteropPolicyGuard
from .reliability import InteropReliabilityBridge
from .transport import InMemoryInteropTransport, InteropTransport

__all__ = [
    "A2AAdapter",
    "SUPPORTED_A2A_VERSION",
    "CapabilityDecision",
    "ExternalCapability",
    "ExternalProvenance",
    "ExternalResult",
    "ExternalTaskRequest",
    "BoundedInteroperabilityGateway",
    "MCPAdapter",
    "SUPPORTED_MCP_VERSION",
    "InteropPolicyDecision",
    "InteropPolicyGuard",
    "InteropReliabilityBridge",
    "InMemoryInteropTransport",
    "InteropTransport",
]
