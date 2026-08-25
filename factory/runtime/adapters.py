from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Protocol


class ProviderAdapter(Protocol):
    provider_id: str

    def invoke(self, *, task_id: str, input_payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class WorkspaceLease:
    workspace_id: str
    mission_id: str
    task_id: str
    write_scopes: tuple[str, ...]


class WorkspaceIsolation:
    """Declares isolated work ownership before a concrete sandbox provider exists."""

    def lease(
        self, *, mission_id: str, task_id: str, write_scopes: tuple[str, ...]
    ) -> WorkspaceLease:
        if not mission_id or not task_id:
            raise ValueError("mission_id and task_id are required")
        normalized = tuple(sorted(set(scope.strip() for scope in write_scopes if scope.strip())))
        digest = hashlib.sha256(f"{mission_id}:{task_id}".encode("utf-8")).hexdigest()[:12]
        return WorkspaceLease(
            workspace_id=f"ws-{digest}",
            mission_id=mission_id,
            task_id=task_id,
            write_scopes=normalized,
        )
