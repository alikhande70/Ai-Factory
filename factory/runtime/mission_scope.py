from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .catalog import SQLiteRuntimeCatalog


@dataclass(frozen=True)
class MissionScopedCatalog:
    """Mission-bound facade over shared runtime persistence.

    The underlying catalog may serve many missions in one process/database. This
    facade prevents callers from supplying arbitrary mission IDs after binding,
    reducing accidental or malicious cross-mission reads/writes at the API seam.
    Global agent registry operations intentionally remain outside this facade.
    """

    catalog: SQLiteRuntimeCatalog
    mission_id: str

    def __post_init__(self) -> None:
        if not self.mission_id:
            raise ValueError("mission_id is required")

    def add_artifact(
        self,
        *,
        artifact_id: str,
        content: str,
        created_by: str,
        media_type: str = "text/plain",
    ) -> dict[str, Any]:
        return self.catalog.add_artifact(
            mission_id=self.mission_id,
            artifact_id=artifact_id,
            content=content,
            created_by=created_by,
            media_type=media_type,
        )

    def latest_artifact(self, artifact_id: str) -> dict[str, Any]:
        return self.catalog.latest_artifact(self.mission_id, artifact_id)

    def set_budget(self, limit_units: int) -> None:
        self.catalog.set_budget(self.mission_id, limit_units)

    def consume_budget(self, units: int) -> tuple[int, int]:
        return self.catalog.consume_budget(self.mission_id, units)

    def propose_action(
        self,
        *,
        proposal_id: str,
        action_type: str,
        target: str,
        protected: bool,
    ) -> None:
        self.catalog.propose_action(
            proposal_id=proposal_id,
            mission_id=self.mission_id,
            action_type=action_type,
            target=target,
            protected=protected,
        )

    def approval_status(self, proposal_id: str) -> str:
        if not proposal_id:
            raise ValueError("proposal_id is required")
        return self.catalog.approval_status(proposal_id, mission_id=self.mission_id)

    def decide_action(self, proposal_id: str, *, approved: bool, decided_by: str) -> str:
        if not proposal_id:
            raise ValueError("proposal_id is required")
        return self.catalog.decide_action(
            proposal_id,
            approved=approved,
            decided_by=decided_by,
            mission_id=self.mission_id,
        )
