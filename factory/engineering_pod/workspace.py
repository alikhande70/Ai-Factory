from __future__ import annotations

from dataclasses import dataclass
import re

from .contracts import ImplementationWorkPackage

_SAFE = re.compile(r"[^a-z0-9._-]+")


def _slug(value: str) -> str:
    result = _SAFE.sub("-", value.strip().lower()).strip("-.")
    if not result:
        raise ValueError("workspace identifier component cannot be empty")
    return result


@dataclass(frozen=True)
class WorkspaceAssignment:
    workspace_id: str
    mission_id: str
    package_id: str
    owner_agent: str
    branch_name: str
    write_scopes: tuple[str, ...]

    def validate_for(self, package: ImplementationWorkPackage) -> None:
        package.validate()
        if self.mission_id != package.mission_id:
            raise ValueError("workspace mission_id mismatch")
        if self.package_id != package.package_id:
            raise ValueError("workspace package_id mismatch")
        if self.owner_agent != package.owner_agent:
            raise ValueError("workspace owner_agent mismatch")
        if self.write_scopes != package.write_scopes:
            raise ValueError("workspace scopes must match package scopes")
        if not self.workspace_id.strip() or not self.branch_name.strip():
            raise ValueError("workspace_id and branch_name are required")
        if self.workspace_id != f"{package.mission_id}:{package.package_id}":
            raise ValueError("workspace_id must preserve canonical mission/package identity")
        if self.branch_name.startswith("/") or self.branch_name.endswith("/") or ".." in self.branch_name:
            raise ValueError("unsafe branch name")


class WorkspaceAllocator:
    branch_prefix = "factory"

    def allocate(self, package: ImplementationWorkPackage) -> WorkspaceAssignment:
        package.validate()
        mission_slug = _slug(package.mission_id)
        package_slug = _slug(package.package_id)
        assignment = WorkspaceAssignment(
            workspace_id=f"{package.mission_id}:{package.package_id}",
            mission_id=package.mission_id,
            package_id=package.package_id,
            owner_agent=package.owner_agent,
            branch_name=f"{self.branch_prefix}/{mission_slug}/{package_slug}",
            write_scopes=package.write_scopes,
        )
        assignment.validate_for(package)
        return assignment
