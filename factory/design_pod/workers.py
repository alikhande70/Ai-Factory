from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import AcceptanceCriterion, ArchitectureDecision, ProductRequirement, UXFlow


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


class ProductArchitectWorker(Protocol):
    agent_id: str

    def design_product(self, *, mission_id: str, objective: str) -> ProductDesignOutput:
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
