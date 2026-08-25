from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


class PolicyEngineV0:
    """Deterministic authorization boundary used before side-effecting work."""

    def authorize(
        self,
        *,
        capability_required: str,
        agent_capabilities: tuple[str, ...],
        protected: bool,
        approval_status: str | None,
        budget_available: bool,
    ) -> PolicyDecision:
        if capability_required not in set(agent_capabilities):
            return PolicyDecision(False, "missing_capability")
        if not budget_available:
            return PolicyDecision(False, "budget_exhausted")
        if protected and approval_status != "APPROVED":
            return PolicyDecision(False, "human_approval_required")
        return PolicyDecision(True, "allowed")
