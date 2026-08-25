from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from factory.design_pod.contracts import DesignBundle

from .contracts import EvidenceManifest, ImplementationWorkPackage
from .validator import EngineeringFinding


@dataclass(frozen=True)
class EngineeringPlan:
    packages: tuple[ImplementationWorkPackage, ...]


@dataclass(frozen=True)
class EngineeringRevisionRequest:
    round_number: int
    findings: tuple[EngineeringFinding, ...]


class EngineeringPlannerWorker(Protocol):
    agent_id: str

    def plan_engineering(self, *, design: DesignBundle) -> EngineeringPlan:
        ...


class RevisableEngineeringPlannerWorker(EngineeringPlannerWorker, Protocol):
    def revise_engineering_plan(
        self,
        *,
        design: DesignBundle,
        plan: EngineeringPlan,
        request: EngineeringRevisionRequest,
    ) -> EngineeringPlan:
        ...


class EngineeringWorker(Protocol):
    agent_id: str
    discipline: str

    def implement(
        self,
        *,
        design: DesignBundle,
        package: ImplementationWorkPackage,
        workspace_id: str,
    ) -> EvidenceManifest:
        ...


class RevisableEngineeringWorker(EngineeringWorker, Protocol):
    def revise_implementation(
        self,
        *,
        design: DesignBundle,
        package: ImplementationWorkPackage,
        workspace_id: str,
        previous_evidence: EvidenceManifest,
        request: EngineeringRevisionRequest,
    ) -> EvidenceManifest:
        ...
