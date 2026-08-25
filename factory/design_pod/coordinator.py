from __future__ import annotations

from dataclasses import asdict
import json

from factory.runtime.catalog import SQLiteRuntimeCatalog

from .contracts import DesignBundle
from .validator import DesignBundleValidator
from .workers import ProductArchitectWorker, SystemArchitectWorker, UXWorker


class DesignPodCoordinator:
    """Coordinates bounded design workers; validation remains deterministic."""

    def __init__(
        self,
        *,
        product_worker: ProductArchitectWorker,
        architecture_worker: SystemArchitectWorker,
        ux_worker: UXWorker,
        validator: DesignBundleValidator | None = None,
        catalog: SQLiteRuntimeCatalog | None = None,
    ) -> None:
        self.product_worker = product_worker
        self.architecture_worker = architecture_worker
        self.ux_worker = ux_worker
        self.validator = validator or DesignBundleValidator()
        self.catalog = catalog

    def run(self, *, mission_id: str, objective: str, created_by: str = "DESIGN-POD") -> DesignBundle:
        if not mission_id or not objective.strip():
            raise ValueError("mission_id and objective are required")

        product = self.product_worker.design_product(mission_id=mission_id, objective=objective)
        architecture = self.architecture_worker.design_architecture(
            mission_id=mission_id,
            objective=objective,
            product=product,
        )
        ux = self.ux_worker.design_ux(
            mission_id=mission_id,
            objective=objective,
            product=product,
        )

        bundle = DesignBundle(
            mission_id=mission_id,
            product_summary=product.product_summary,
            non_goals=product.non_goals,
            requirements=product.requirements,
            acceptance_criteria=product.acceptance_criteria,
            architecture_decisions=architecture.decisions,
            ux_flows=ux.flows,
            assumptions=product.assumptions,
            risks=tuple(dict.fromkeys(product.risks + architecture.risks + ux.risks)),
        )

        findings = self.validator.validate(bundle)
        blockers = [item for item in findings if item.severity == "BLOCKING"]
        if blockers:
            codes = ",".join(item.code for item in blockers)
            raise RuntimeError(f"design_bundle_not_build_ready:{codes}")

        if self.catalog is not None:
            self.catalog.add_artifact(
                mission_id=mission_id,
                artifact_id="design-bundle",
                content=json.dumps(asdict(bundle), sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                created_by=created_by,
                media_type="application/vnd.ai-factory.design-bundle+json",
            )
        return bundle
