from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProductRequirement:
    requirement_id: str
    statement: str
    priority: str
    source: str = "MISSION"

    def validate(self) -> None:
        if not self.requirement_id or not self.statement:
            raise ValueError("requirement_id and statement are required")
        if self.priority not in {"MUST", "SHOULD", "COULD", "WONT"}:
            raise ValueError("invalid requirement priority")


@dataclass(frozen=True)
class AcceptanceCriterion:
    criterion_id: str
    requirement_id: str
    statement: str
    verification_method: str

    def validate(self) -> None:
        if not all((self.criterion_id, self.requirement_id, self.statement, self.verification_method)):
            raise ValueError("acceptance criterion required fields missing")


@dataclass(frozen=True)
class ArchitectureDecision:
    decision_id: str
    title: str
    decision: str
    rationale: str
    requirement_ids: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not all((self.decision_id, self.title, self.decision, self.rationale)):
            raise ValueError("architecture decision required fields missing")


@dataclass(frozen=True)
class UXFlow:
    flow_id: str
    title: str
    actor: str
    steps: tuple[str, ...]
    requirement_ids: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not all((self.flow_id, self.title, self.actor)):
            raise ValueError("ux flow required fields missing")
        if not self.steps:
            raise ValueError("ux flow requires at least one step")


@dataclass(frozen=True)
class DesignBundle:
    mission_id: str
    product_summary: str
    non_goals: tuple[str, ...]
    requirements: tuple[ProductRequirement, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    architecture_decisions: tuple[ArchitectureDecision, ...]
    ux_flows: tuple[UXFlow, ...]
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    risks: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.mission_id or not self.product_summary:
            raise ValueError("mission_id and product_summary are required")
        if not self.requirements:
            raise ValueError("design bundle requires at least one requirement")
        for item in self.requirements:
            item.validate()
        for item in self.acceptance_criteria:
            item.validate()
        for item in self.architecture_decisions:
            item.validate()
        for item in self.ux_flows:
            item.validate()
