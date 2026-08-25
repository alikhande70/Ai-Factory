from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


ControlStatus = Literal["PASS", "FAIL", "UNVERIFIED", "NOT_APPLICABLE"]
ReadinessStage = Literal["NOT_QUALIFIED", "CODE_QUALIFIED", "PRODUCTION_READY"]

MANDATORY_CODE_CONTROLS = (
    "multi_mission_isolation",
    "backup_restore_integrity",
    "secret_reference_boundary",
    "audit_archival_integrity",
    "incident_response_state_machine",
    "supply_chain_inventory",
    "slo_evidence_contract",
    "ci_performance_regression",
)

MANDATORY_PRODUCTION_CONTROLS = (
    "github_branch_protection",
    "production_secret_provider",
    "offsite_recovery",
    "production_slo_evidence",
)


@dataclass(frozen=True)
class ReadinessControl:
    control_id: str
    status: ControlStatus
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.control_id.strip():
            raise ValueError("control_id is required")
        if self.status not in {"PASS", "FAIL", "UNVERIFIED", "NOT_APPLICABLE"}:
            raise ValueError("invalid readiness control status")
        if self.status == "PASS" and (self.evidence_ref is None or not self.evidence_ref.strip()):
            raise ValueError("PASS readiness control requires evidence_ref")


@dataclass(frozen=True)
class ReadinessBlocker:
    control_id: str
    status: str
    scope: str


@dataclass(frozen=True)
class ReleaseReadinessReport:
    stage: ReadinessStage
    code_qualified: bool
    production_ready: bool
    controls: tuple[ReadinessControl, ...]
    blockers: tuple[ReadinessBlocker, ...]

    def assert_production_ready(self) -> None:
        if not self.production_ready:
            raise RuntimeError("production_readiness_not_proven")


def _normalize(controls: Iterable[ReadinessControl]) -> dict[str, ReadinessControl]:
    result: dict[str, ReadinessControl] = {}
    for control in controls:
        if control.control_id in result:
            raise ValueError(f"duplicate readiness control:{control.control_id}")
        result[control.control_id] = control
    return result


def evaluate_release_readiness(
    controls: Iterable[ReadinessControl],
    *,
    required_code_controls: tuple[str, ...] = MANDATORY_CODE_CONTROLS,
    required_production_controls: tuple[str, ...] = MANDATORY_PRODUCTION_CONTROLS,
) -> ReleaseReadinessReport:
    provided = _normalize(controls)
    blockers: list[ReadinessBlocker] = []

    def status_for(control_id: str) -> str:
        control = provided.get(control_id)
        return "UNVERIFIED" if control is None else control.status

    code_qualified = True
    for control_id in required_code_controls:
        status = status_for(control_id)
        if status != "PASS":
            code_qualified = False
            blockers.append(ReadinessBlocker(control_id, status, "CODE"))

    production_controls_pass = True
    for control_id in required_production_controls:
        status = status_for(control_id)
        if status != "PASS":
            production_controls_pass = False
            blockers.append(ReadinessBlocker(control_id, status, "PRODUCTION"))

    production_ready = code_qualified and production_controls_pass
    if production_ready:
        stage: ReadinessStage = "PRODUCTION_READY"
    elif code_qualified:
        stage = "CODE_QUALIFIED"
    else:
        stage = "NOT_QUALIFIED"

    # Keep supplied controls ordered deterministically; missing controls are represented
    # in blockers instead of being silently fabricated into canonical evidence.
    normalized_controls = tuple(provided[key] for key in sorted(provided))
    return ReleaseReadinessReport(
        stage=stage,
        code_qualified=code_qualified,
        production_ready=production_ready,
        controls=normalized_controls,
        blockers=tuple(sorted(blockers, key=lambda item: (item.scope, item.control_id))),
    )
