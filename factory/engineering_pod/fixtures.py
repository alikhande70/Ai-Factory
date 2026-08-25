from __future__ import annotations

from dataclasses import dataclass

from factory.design_pod.contracts import DesignBundle

from .contracts import DISCIPLINE_OWNER, ENGINEERING_DISCIPLINES, ImplementationWorkPackage
from .workers import EngineeringPlan


@dataclass(frozen=True)
class FixturePackageSpec:
    """Deterministic evaluation-only mapping from design requirements to engineering work."""

    package_id: str
    discipline: str
    requirement_ids: tuple[str, ...]
    write_scopes: tuple[str, ...]
    expected_artifacts: tuple[str, ...]
    verification_methods: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    objective: str = "Implement controlled evaluation package"

    def validate(self) -> None:
        if not self.package_id or not self.objective.strip():
            raise ValueError("fixture package_id and objective are required")
        if self.discipline not in ENGINEERING_DISCIPLINES:
            raise ValueError(f"unknown fixture discipline: {self.discipline}")
        if not self.requirement_ids:
            raise ValueError("fixture must map at least one requirement")
        if not self.write_scopes or not self.expected_artifacts or not self.verification_methods:
            raise ValueError("fixture package requires scopes, artifacts and verification")


class DesignToEngineeringFixturePlanner:
    """Builds a reproducible EngineeringPlan from an explicit evaluation fixture.

    This is deliberately not a heuristic production planner. The mapping is explicit so
    qualification tests can prove DesignBundle traceability without hiding decisions in
    free-form model output.
    """

    agent_id = "A01-ORCHESTRATOR"

    def __init__(self, specs: tuple[FixturePackageSpec, ...]) -> None:
        if not specs:
            raise ValueError("at least one fixture package spec is required")
        self.specs = specs

    def plan_engineering(self, *, design: DesignBundle) -> EngineeringPlan:
        design.validate()
        known_requirements = {item.requirement_id for item in design.requirements}
        package_ids = {item.package_id for item in self.specs}
        if len(package_ids) != len(self.specs):
            raise ValueError("fixture package IDs must be unique")

        packages: list[ImplementationWorkPackage] = []
        for spec in self.specs:
            spec.validate()
            unknown_requirements = set(spec.requirement_ids) - known_requirements
            if unknown_requirements:
                raise ValueError(
                    "fixture references unknown requirements: " + ",".join(sorted(unknown_requirements))
                )
            unknown_dependencies = set(spec.depends_on) - package_ids
            if unknown_dependencies:
                raise ValueError(
                    "fixture references unknown dependencies: " + ",".join(sorted(unknown_dependencies))
                )
            packages.append(
                ImplementationWorkPackage(
                    package_id=spec.package_id,
                    mission_id=design.mission_id,
                    owner_agent=DISCIPLINE_OWNER[spec.discipline],
                    discipline=spec.discipline,
                    objective=spec.objective,
                    requirement_ids=spec.requirement_ids,
                    depends_on=spec.depends_on,
                    write_scopes=spec.write_scopes,
                    expected_artifacts=spec.expected_artifacts,
                    verification_methods=spec.verification_methods,
                )
            )
        return EngineeringPlan(tuple(packages))
