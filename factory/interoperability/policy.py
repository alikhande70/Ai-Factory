from __future__ import annotations

from dataclasses import dataclass

from factory.runtime.policy import PolicyEngineV0

from .contracts import ExternalCapability


@dataclass(frozen=True)
class InteropPolicyDecision:
    allowed: bool
    reason: str
    capability_id: str

    def validate(self) -> None:
        if not self.reason.strip() or not self.capability_id.strip():
            raise ValueError("interop policy decision reason and capability_id are required")


class InteropPolicyGuard:
    """Intersects external capabilities with deterministic Factory policy."""

    def __init__(self, policy_engine: PolicyEngineV0 | None = None) -> None:
        self.policy_engine = policy_engine or PolicyEngineV0()

    def authorize(
        self,
        *,
        capability: ExternalCapability,
        factory_capabilities: tuple[str, ...],
        protected: bool,
        approval_status: str | None,
        budget_available: bool,
    ) -> InteropPolicyDecision:
        capability.validate()
        policy = self.policy_engine.authorize(
            capability_required=capability.required_factory_capability,
            agent_capabilities=factory_capabilities,
            protected=protected,
            approval_status=approval_status,
            budget_available=budget_available,
        )
        decision = InteropPolicyDecision(
            allowed=policy.allowed,
            reason=policy.reason,
            capability_id=capability.capability_id,
        )
        decision.validate()
        return decision
