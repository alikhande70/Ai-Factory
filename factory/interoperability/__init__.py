"""Protocol-neutral interoperability boundary for external tools and agents."""

from .a2a import A2AAdapter, SUPPORTED_A2A_VERSION
from .contracts import (
    CapabilityDecision,
    ExternalCapability,
    ExternalProvenance,
    ExternalResult,
    ExternalTaskRequest,
)
from .mcp import MCPAdapter, SUPPORTED_MCP_VERSION
from .policy import InteropPolicyDecision, InteropPolicyGuard
from .reliability import InteropReliabilityBridge

__all__ = [
    "A2AAdapter",
    "SUPPORTED_A2A_VERSION",
    "CapabilityDecision",
    "ExternalCapability",
    "ExternalProvenance",
    "ExternalResult",
    "ExternalTaskRequest",
    "MCPAdapter",
    "SUPPORTED_MCP_VERSION",
    "InteropPolicyDecision",
    "InteropPolicyGuard",
    "InteropReliabilityBridge",
]
