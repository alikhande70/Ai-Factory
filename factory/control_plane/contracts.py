from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceKind(str, Enum):
    TEST = "TEST"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"
    DIFF = "DIFF"
    LOG = "LOG"
    ARTIFACT = "ARTIFACT"
    MANUAL_CHECK = "MANUAL_CHECK"


class ObjectionSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    mission_id: str
    task_id: str
    producer_id: str
    kind: EvidenceKind
    summary: str
    artifact_refs: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not all((self.evidence_id, self.mission_id, self.task_id, self.producer_id, self.summary)):
            raise ValueError("evidence required fields missing")


@dataclass(frozen=True)
class ObjectionRecord:
    objection_id: str
    mission_id: str
    task_id: str
    raised_by: str
    severity: ObjectionSeverity
    reason: str

    def validate(self) -> None:
        if not all((self.objection_id, self.mission_id, self.task_id, self.raised_by, self.reason)):
            raise ValueError("objection required fields missing")


@dataclass(frozen=True)
class ReviewRecord:
    review_id: str
    mission_id: str
    task_id: str
    reviewer_id: str
    evidence_ids: tuple[str, ...]
    verdict: str
    notes: str = ""

    def validate(self, worker_ids: tuple[str, ...] = ()) -> None:
        if self.verdict not in {"APPROVE", "CHANGES_REQUESTED", "REJECT"}:
            raise ValueError("invalid review verdict")
        if not self.evidence_ids:
            raise ValueError("review requires evidence")
        if self.reviewer_id in set(worker_ids):
            raise ValueError("reviewer cannot review own task work")


@dataclass(frozen=True)
class TypedEvent:
    event_id: str
    mission_id: str
    actor_id: str
    event_type: str
    payload: dict[str, Any]

    def validate(self) -> None:
        if not all((self.event_id, self.mission_id, self.actor_id, self.event_type)):
            raise ValueError("event required fields missing")
