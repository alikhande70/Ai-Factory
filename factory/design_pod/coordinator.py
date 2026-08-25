from __future__ import annotations

from dataclasses import asdict
import json

from factory.runtime.catalog import SQLiteRuntimeCatalog

from .contracts import DesignBundle
from .validator import DesignBundleValidator, ValidationFinding
from .workers import (
    ArchitectureDesignOutput,
    ProductArchitectWorker,
    ProductDesignOutput,
    RevisionRequest,
    SystemArchitectWorker,
    UXDesignOutput,
    UXWorker,
)


_PRODUCT_FINDINGS = {
    "DUPLICATE_REQUIREMENT_ID",
    "DUPLICATE_CRITERION_ID",
    "ORPHAN_ACCEPTANCE_CRITERION",
    "MUST_WITHOUT_ACCEPTANCE_CRITERION",
}
_ARCHITECTURE_FINDINGS = {"ARCHITECTURE_UNKNOWN_REQUIREMENT"}
_UX_FINDINGS = {"UX_UNKNOWN_REQUIREMENT"}
_SHARED_DESIGN_FINDINGS = {"MUST_WITHOUT_DESIGN_COVERAGE"}


class DesignPodCoordinator:
    """Coordinates bounded design workers; validation remains deterministic.

    The coordinator may ask the responsible worker to revise a blocked output,
    but it cannot weaken validator findings or revise forever. Product changes
    invalidate architecture and UX, so downstream design is regenerated from
    the new product output before the next validation pass.
    """

    def __init__(
        self,
        *,
        product_worker: ProductArchitectWorker,
        architecture_worker: SystemArchitectWorker,
        ux_worker: UXWorker,
        validator: DesignBundleValidator | None = None,
        catalog: SQLiteRuntimeCatalog | None = None,
        max_revision_rounds: int = 2,
    ) -> None:
        if max_revision_rounds < 0:
            raise ValueError("max_revision_rounds must be >= 0")
        self.product_worker = product_worker
        self.architecture_worker = architecture_worker
        self.ux_worker = ux_worker
        self.validator = validator or DesignBundleValidator()
        self.catalog = catalog
        self.max_revision_rounds = max_revision_rounds

    @staticmethod
    def _bundle(
        *,
        mission_id: str,
        product: ProductDesignOutput,
        architecture: ArchitectureDesignOutput,
        ux: UXDesignOutput,
    ) -> DesignBundle:
        return DesignBundle(
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

    @staticmethod
    def _blocking(findings: tuple[ValidationFinding, ...]) -> tuple[ValidationFinding, ...]:
        return tuple(item for item in findings if item.severity == "BLOCKING")

    @staticmethod
    def _fingerprint(bundle: DesignBundle) -> str:
        return json.dumps(asdict(bundle), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _select(findings: tuple[ValidationFinding, ...], codes: set[str]) -> tuple[ValidationFinding, ...]:
        return tuple(item for item in findings if item.code in codes)

    def _revise(
        self,
        *,
        mission_id: str,
        objective: str,
        round_number: int,
        blockers: tuple[ValidationFinding, ...],
        product: ProductDesignOutput,
        architecture: ArchitectureDesignOutput,
        ux: UXDesignOutput,
    ) -> tuple[ProductDesignOutput, ArchitectureDesignOutput, UXDesignOutput]:
        known_codes = _PRODUCT_FINDINGS | _ARCHITECTURE_FINDINGS | _UX_FINDINGS | _SHARED_DESIGN_FINDINGS
        unknown = sorted({item.code for item in blockers if item.code not in known_codes})
        if unknown:
            raise RuntimeError(f"design_revision_unroutable:{','.join(unknown)}")

        product_findings = self._select(blockers, _PRODUCT_FINDINGS)
        architecture_findings = self._select(blockers, _ARCHITECTURE_FINDINGS | _SHARED_DESIGN_FINDINGS)
        ux_findings = self._select(blockers, _UX_FINDINGS | _SHARED_DESIGN_FINDINGS)

        if product_findings:
            revise_product = getattr(self.product_worker, "revise_product", None)
            if revise_product is None:
                raise RuntimeError("design_revision_unsupported:A02-PRODUCT")
            product = revise_product(
                mission_id=mission_id,
                objective=objective,
                product=product,
                request=RevisionRequest(round_number=round_number, findings=product_findings),
            )
            # Product is upstream truth for both dependent design roles. Never
            # keep architecture/UX that was produced against a superseded PRD.
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
            return product, architecture, ux

        if architecture_findings:
            revise_architecture = getattr(self.architecture_worker, "revise_architecture", None)
            if revise_architecture is None:
                raise RuntimeError("design_revision_unsupported:A03-ARCH")
            architecture = revise_architecture(
                mission_id=mission_id,
                objective=objective,
                product=product,
                architecture=architecture,
                request=RevisionRequest(round_number=round_number, findings=architecture_findings),
            )

        if ux_findings:
            revise_ux = getattr(self.ux_worker, "revise_ux", None)
            if revise_ux is None:
                raise RuntimeError("design_revision_unsupported:A04-UX")
            ux = revise_ux(
                mission_id=mission_id,
                objective=objective,
                product=product,
                ux=ux,
                request=RevisionRequest(round_number=round_number, findings=ux_findings),
            )

        return product, architecture, ux

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

        bundle = self._bundle(mission_id=mission_id, product=product, architecture=architecture, ux=ux)
        for round_number in range(0, self.max_revision_rounds + 1):
            findings = self.validator.validate(bundle)
            blockers = self._blocking(findings)
            if not blockers:
                if self.catalog is not None:
                    self.catalog.add_artifact(
                        mission_id=mission_id,
                        artifact_id="design-bundle",
                        content=self._fingerprint(bundle),
                        created_by=created_by,
                        media_type="application/vnd.ai-factory.design-bundle+json",
                    )
                return bundle

            if round_number >= self.max_revision_rounds:
                codes = ",".join(item.code for item in blockers)
                raise RuntimeError(f"design_revision_exhausted:{codes}")

            before = self._fingerprint(bundle)
            product, architecture, ux = self._revise(
                mission_id=mission_id,
                objective=objective,
                round_number=round_number + 1,
                blockers=blockers,
                product=product,
                architecture=architecture,
                ux=ux,
            )
            bundle = self._bundle(mission_id=mission_id, product=product, architecture=architecture, ux=ux)
            if self._fingerprint(bundle) == before:
                codes = ",".join(item.code for item in blockers)
                raise RuntimeError(f"design_revision_no_progress:{codes}")

        raise AssertionError("unreachable revision loop")
