from __future__ import annotations

from dataclasses import asdict
import json

from factory.design_pod.contracts import DesignBundle
from factory.engineering_pod.integration import IntegrationManifest
from factory.runtime.catalog import SQLiteRuntimeCatalog

from .contracts import ASSURANCE_ROLES, AssuranceDecision, AssuranceReport
from .validator import AssuranceValidator
from .workers import AssuranceWorker


class AssurancePodCoordinator:
    """Runs independent assurance roles and persists the deterministic decision."""

    def __init__(
        self,
        *,
        workers: tuple[AssuranceWorker, ...],
        validator: AssuranceValidator | None = None,
        catalog: SQLiteRuntimeCatalog | None = None,
    ) -> None:
        self.workers = {worker.agent_id: worker for worker in workers}
        self.validator = validator or AssuranceValidator()
        self.catalog = catalog

    def run(
        self,
        *,
        design: DesignBundle,
        integration: IntegrationManifest,
        implementation_agent_ids: tuple[str, ...],
        created_by: str = "ASSURANCE-POD",
    ) -> tuple[tuple[AssuranceReport, ...], AssuranceDecision]:
        design.validate()
        integration.validate()
        if design.mission_id != integration.mission_id:
            raise ValueError("design/integration mission mismatch")

        reports: list[AssuranceReport] = []
        for reviewer_id in sorted(ASSURANCE_ROLES):
            worker = self.workers.get(reviewer_id)
            if worker is None:
                raise RuntimeError(f"assurance_worker_missing:{reviewer_id}")
            report = worker.review(design=design, integration=integration)
            if report.reviewer_agent != reviewer_id:
                raise RuntimeError(f"assurance_worker_identity_mismatch:{reviewer_id}")
            report.validate()
            reports.append(report)
            if self.catalog is not None:
                self.catalog.add_artifact(
                    mission_id=design.mission_id,
                    artifact_id=f"assurance-report-{reviewer_id.lower()}",
                    content=json.dumps(asdict(report), sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                    created_by=created_by,
                    media_type="application/vnd.ai-factory.assurance-report+json",
                )

        decision = self.validator.decide(
            mission_id=design.mission_id,
            reports=tuple(reports),
            implementation_agent_ids=implementation_agent_ids,
        )
        if self.catalog is not None:
            self.catalog.add_artifact(
                mission_id=design.mission_id,
                artifact_id="assurance-decision",
                content=json.dumps(asdict(decision), sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                created_by=created_by,
                media_type="application/vnd.ai-factory.assurance-decision+json",
            )
        return tuple(reports), decision
