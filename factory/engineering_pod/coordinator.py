from __future__ import annotations

from dataclasses import asdict
import json

from factory.design_pod.contracts import DesignBundle
from factory.runtime.catalog import SQLiteRuntimeCatalog

from .contracts import DISCIPLINE_OWNER, EvidenceManifest, ImplementationWorkPackage
from .integration import EngineeringIntegrationValidator, IntegrationManifest
from .validator import EngineeringFinding, EngineeringPlanValidator
from .workers import EngineeringPlan, EngineeringPlannerWorker, EngineeringRevisionRequest, EngineeringWorker
from .workspace import WorkspaceAllocator, WorkspaceAssignment


class EngineeringPodCoordinator:
    """Bounded coordinator for DesignBundle -> plan -> isolated execution -> evidence.

    Planning and implementation may be probabilistic, but plan/evidence acceptance is
    deterministic. The coordinator cannot widen scopes, invent evidence, or bypass a
    blocking finding. Each package is dispatched only to the declared discipline owner.
    """

    def __init__(
        self,
        *,
        planner: EngineeringPlannerWorker,
        workers: tuple[EngineeringWorker, ...],
        validator: EngineeringPlanValidator | None = None,
        integration_validator: EngineeringIntegrationValidator | None = None,
        catalog: SQLiteRuntimeCatalog | None = None,
        workspace_allocator: WorkspaceAllocator | None = None,
        max_plan_revision_rounds: int = 2,
        max_implementation_revision_rounds: int = 2,
    ) -> None:
        if max_plan_revision_rounds < 0 or max_implementation_revision_rounds < 0:
            raise ValueError("revision limits must be >= 0")
        self.planner = planner
        self.validator = validator or EngineeringPlanValidator()
        self.integration_validator = integration_validator or EngineeringIntegrationValidator(self.validator)
        self.catalog = catalog
        self.workspace_allocator = workspace_allocator or WorkspaceAllocator()
        self.max_plan_revision_rounds = max_plan_revision_rounds
        self.max_implementation_revision_rounds = max_implementation_revision_rounds
        self.workers = {worker.agent_id: worker for worker in workers}
        self.workspace_assignments: dict[str, WorkspaceAssignment] = {}

    @staticmethod
    def _blocking(findings: tuple[EngineeringFinding, ...]) -> tuple[EngineeringFinding, ...]:
        return tuple(item for item in findings if item.severity == "BLOCKING")

    @staticmethod
    def _plan_fingerprint(plan: EngineeringPlan) -> str:
        return json.dumps(asdict(plan), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _validated_plan(self, *, design: DesignBundle) -> EngineeringPlan:
        plan = self.planner.plan_engineering(design=design)
        for round_number in range(self.max_plan_revision_rounds + 1):
            findings = self.validator.validate(design=design, packages=plan.packages)
            blockers = self._blocking(findings)
            if not blockers:
                return plan
            if round_number >= self.max_plan_revision_rounds:
                raise RuntimeError("engineering_plan_revision_exhausted:" + ",".join(item.code for item in blockers))
            revise = getattr(self.planner, "revise_engineering_plan", None)
            if revise is None:
                raise RuntimeError("engineering_plan_revision_unsupported")
            before = self._plan_fingerprint(plan)
            plan = revise(
                design=design,
                plan=plan,
                request=EngineeringRevisionRequest(round_number=round_number + 1, findings=blockers),
            )
            if self._plan_fingerprint(plan) == before:
                raise RuntimeError("engineering_plan_revision_no_progress")
        raise AssertionError("unreachable plan revision loop")

    def _execution_order(self, packages: tuple[ImplementationWorkPackage, ...]) -> tuple[ImplementationWorkPackage, ...]:
        remaining = {package.package_id: package for package in packages}
        emitted: list[ImplementationWorkPackage] = []
        completed: set[str] = set()
        while remaining:
            ready = sorted(
                (package for package in remaining.values() if set(package.depends_on) <= completed),
                key=lambda package: package.package_id,
            )
            if not ready:
                raise RuntimeError("engineering_dependency_deadlock")
            for package in ready:
                emitted.append(package)
                completed.add(package.package_id)
                remaining.pop(package.package_id)
        return tuple(emitted)

    def _run_package(self, *, design: DesignBundle, package: ImplementationWorkPackage) -> EvidenceManifest:
        expected_owner = DISCIPLINE_OWNER[package.discipline]
        worker = self.workers.get(expected_owner)
        if worker is None:
            raise RuntimeError(f"engineering_worker_missing:{expected_owner}")
        if worker.agent_id != package.owner_agent or worker.discipline != package.discipline:
            raise RuntimeError(f"engineering_worker_identity_mismatch:{package.package_id}")

        assignment = self.workspace_allocator.allocate(package)
        assignment.validate_for(package)
        self.workspace_assignments[package.package_id] = assignment
        evidence = worker.implement(design=design, package=package, workspace_id=assignment.workspace_id)
        for round_number in range(self.max_implementation_revision_rounds + 1):
            blockers = self._blocking(self.validator.validate_evidence(package=package, evidence=evidence))
            if not blockers:
                return evidence
            if round_number >= self.max_implementation_revision_rounds:
                raise RuntimeError(
                    "engineering_implementation_revision_exhausted:"
                    + package.package_id
                    + ":"
                    + ",".join(item.code for item in blockers)
                )
            revise = getattr(worker, "revise_implementation", None)
            if revise is None:
                raise RuntimeError(f"engineering_implementation_revision_unsupported:{package.package_id}")
            previous = evidence
            evidence = revise(
                design=design,
                package=package,
                workspace_id=assignment.workspace_id,
                previous_evidence=previous,
                request=EngineeringRevisionRequest(round_number=round_number + 1, findings=blockers),
            )
            if evidence == previous:
                raise RuntimeError(f"engineering_implementation_revision_no_progress:{package.package_id}")
        raise AssertionError("unreachable implementation revision loop")

    def _execute(
        self,
        *,
        design: DesignBundle,
        created_by: str,
    ) -> tuple[EngineeringPlan, tuple[ImplementationWorkPackage, ...], tuple[EvidenceManifest, ...]]:
        design.validate()
        plan = self._validated_plan(design=design)
        execution_order = self._execution_order(plan.packages)
        self.workspace_assignments = {}
        evidence: list[EvidenceManifest] = []
        for package in execution_order:
            result = self._run_package(design=design, package=package)
            evidence.append(result)
            if self.catalog is not None:
                self.catalog.add_artifact(
                    mission_id=design.mission_id,
                    artifact_id=f"engineering-evidence-{package.package_id.lower()}",
                    content=json.dumps(asdict(result), sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                    created_by=created_by,
                    media_type="application/vnd.ai-factory.engineering-evidence+json",
                )
        return plan, execution_order, tuple(evidence)

    def run(self, *, design: DesignBundle, created_by: str = "ENGINEERING-POD") -> tuple[EvidenceManifest, ...]:
        _, _, evidence = self._execute(design=design, created_by=created_by)
        return evidence

    def run_integrated(
        self,
        *,
        design: DesignBundle,
        created_by: str = "ENGINEERING-POD",
    ) -> tuple[tuple[EvidenceManifest, ...], IntegrationManifest]:
        plan, execution_order, evidence = self._execute(design=design, created_by=created_by)
        integration = self.integration_validator.integrate(
            mission_id=design.mission_id,
            packages=plan.packages,
            evidence=evidence,
            package_order=tuple(package.package_id for package in execution_order),
        )
        if self.catalog is not None:
            self.catalog.add_artifact(
                mission_id=design.mission_id,
                artifact_id="engineering-integration-manifest",
                content=json.dumps(asdict(integration), sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                created_by=created_by,
                media_type="application/vnd.ai-factory.engineering-integration+json",
            )
        return evidence, integration
