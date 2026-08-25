from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import AcceptanceCriterion, ArchitectureDecision, ProductRequirement, UXFlow
from .validator import ValidationFinding


@dataclass(frozen=True)
class ProductDesignOutput:
    product_summary: str
    non_goals: tuple[str, ...]
    requirements: tuple[ProductRequirement, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    assumptions: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArchitectureDesignOutput:
    decisions: tuple[ArchitectureDecision, ...]
    risks: tuple[str, ...] = ()


@dataclass(frozen=True)
class UXDesignOutput:
    flows: tuple[UXFlow, ...]
    risks: tuple[str, ...] = ()


@dataclass(frozen=True)
class RevisionRequest:
    """Deterministic feedback envelope sent only to the responsible worker.

    Workers receive validator findings, never authority to weaken or rewrite the
    validator. The coordinator owns the revision budget and re-validation loop.
    """

    round_number: int
    findings: tuple[ValidationFinding, ...]


class ProductArchitectWorker(Protocol):
    agent_id: str

    def design_product(self, *, mission_id: str, objective: str) -> ProductDesignOutput:
        ...


class RevisableProductArchitectWorker(ProductArchitectWorker, Protocol):
    def revise_product(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
        request: RevisionRequest,
    ) -> ProductDesignOutput:
        ...


class SystemArchitectWorker(Protocol):
    agent_id: str

    def design_architecture(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
    ) -> ArchitectureDesignOutput:
        ...


class RevisableSystemArchitectWorker(SystemArchitectWorker, Protocol):
    def revise_architecture(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
        architecture: ArchitectureDesignOutput,
        request: RevisionRequest,
    ) -> ArchitectureDesignOutput:
        ...


class UXWorker(Protocol):
    agent_id: str

    def design_ux(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
    ) -> UXDesignOutput:
        ...


class RevisableUXWorker(UXWorker, Protocol):
    def revise_ux(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
        ux: UXDesignOutput,
        request: RevisionRequest,
    ) -> UXDesignOutput:
        ...
