from __future__ import annotations

from dataclasses import dataclass

from .contracts import RecoveryDecision
from .store import SQLiteReliabilityStore


@dataclass(frozen=True)
class MissionRecoveryItem:
    operation_id: str
    action: str
    reason: str

    def validate(self) -> None:
        if not self.operation_id.strip() or not self.reason.strip():
            raise ValueError("recovery item identity and reason are required")
        if self.action not in {"READY", "RETRY", "RECONCILE", "COMPLETE", "STOP"}:
            raise ValueError(f"unknown mission recovery action:{self.action}")


@dataclass(frozen=True)
class MissionRecoveryReport:
    mission_id: str
    items: tuple[MissionRecoveryItem, ...]
    safe_to_continue: bool

    def validate(self) -> None:
        if not self.mission_id.strip() or not self.items:
            raise ValueError("mission recovery report requires mission_id and items")
        ids = [item.operation_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate operation in mission recovery report")
        for item in self.items:
            item.validate()
        expected = all(item.action not in {"RECONCILE", "STOP"} for item in self.items)
        if self.safe_to_continue != expected:
            raise ValueError("safe_to_continue does not match recovery actions")


class MissionRecoveryCoordinator:
    """Reconstructs mission-level next actions from durable operation state only."""

    def __init__(self, store: SQLiteReliabilityStore) -> None:
        self.store = store

    def recover(self, *, mission_id: str, operation_ids: tuple[str, ...]) -> MissionRecoveryReport:
        if not operation_ids:
            raise ValueError("operation_ids are required")
        items: list[MissionRecoveryItem] = []
        for operation_id in operation_ids:
            state = self.store.state(operation_id)
            if state["mission_id"] != mission_id:
                raise ValueError("operation belongs to a different mission")
            status = str(state["status"])
            if status == "READY":
                item = MissionRecoveryItem(operation_id, "READY", "operation_not_started")
            elif status == "COMPLETED":
                item = MissionRecoveryItem(operation_id, "COMPLETE", "operation_already_completed")
            elif status == "STOPPED":
                decision = self.store.latest_decision(operation_id)
                item = MissionRecoveryItem(operation_id, "STOP", decision.reason)
            else:
                decision: RecoveryDecision = self.store.latest_decision(operation_id)
                item = MissionRecoveryItem(operation_id, decision.action, decision.reason)
            item.validate()
            items.append(item)
        report = MissionRecoveryReport(
            mission_id=mission_id,
            items=tuple(items),
            safe_to_continue=all(item.action not in {"RECONCILE", "STOP"} for item in items),
        )
        report.validate()
        return report


@dataclass(frozen=True)
class ReleasePreviewPlan:
    mission_id: str
    candidate_fingerprint: str
    reviewed_fingerprint: str
    assurance_status: str
    rollback_ref: str
    environment: str = "PREVIEW"
    human_approval_granted: bool = False

    def validate(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.mission_id,
                self.candidate_fingerprint,
                self.reviewed_fingerprint,
                self.rollback_ref,
                self.environment,
            )
        ):
            raise ValueError("release preview identity, fingerprints, environment and rollback_ref are required")
        if self.assurance_status != "PASS":
            raise ValueError("release candidate requires assurance PASS")
        if self.candidate_fingerprint != self.reviewed_fingerprint:
            raise ValueError("release candidate fingerprint is not the reviewed fingerprint")
        if self.environment == "PRODUCTION" and not self.human_approval_granted:
            raise ValueError("production release requires explicit human approval")

    @property
    def may_execute(self) -> bool:
        self.validate()
        return self.environment != "PRODUCTION" or self.human_approval_granted
