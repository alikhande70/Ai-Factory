from __future__ import annotations

from dataclasses import dataclass


ENGINEERING_DISCIPLINES = frozenset({"FRONTEND", "BACKEND", "DATABASE", "AI_AUTOMATION"})
DISCIPLINE_OWNER = {
    "FRONTEND": "A05-FRONTEND",
    "BACKEND": "A06-BACKEND",
    "DATABASE": "A07-DATABASE",
    "AI_AUTOMATION": "A08-AI-AUTOMATION",
}


@dataclass(frozen=True)
class ImplementationWorkPackage:
    package_id: str
    mission_id: str
    owner_agent: str
    discipline: str
    objective: str
    requirement_ids: tuple[str, ...]
    depends_on: tuple[str, ...]
    write_scopes: tuple[str, ...]
    expected_artifacts: tuple[str, ...]
    verification_methods: tuple[str, ...]

    def validate(self) -> None:
        if not self.package_id or not self.mission_id or not self.objective.strip():
            raise ValueError("package_id, mission_id and objective are required")
        if self.discipline not in ENGINEERING_DISCIPLINES:
            raise ValueError(f"unknown engineering discipline: {self.discipline}")
        if self.owner_agent != DISCIPLINE_OWNER[self.discipline]:
            raise ValueError("owner_agent does not match engineering discipline")
        if not self.requirement_ids:
            raise ValueError("at least one requirement_id is required")
        if not self.write_scopes:
            raise ValueError("at least one write_scope is required")
        if not self.expected_artifacts:
            raise ValueError("at least one expected_artifact is required")
        if not self.verification_methods:
            raise ValueError("at least one verification_method is required")
        if self.package_id in self.depends_on:
            raise ValueError("work package cannot depend on itself")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("duplicate package dependencies are not allowed")
        if len(self.write_scopes) != len(set(self.write_scopes)):
            raise ValueError("duplicate write scopes are not allowed")


@dataclass(frozen=True)
class VerificationResult:
    verification_id: str
    method: str
    status: str
    evidence_ref: str

    def validate(self) -> None:
        if not self.verification_id or not self.method.strip() or not self.evidence_ref.strip():
            raise ValueError("verification_id, method and evidence_ref are required")
        if self.status not in {"PASS", "FAIL"}:
            raise ValueError("verification status must be PASS or FAIL")


@dataclass(frozen=True)
class EvidenceManifest:
    package_id: str
    changed_paths: tuple[str, ...]
    produced_artifacts: tuple[str, ...]
    verification_results: tuple[VerificationResult, ...]

    def validate(self) -> None:
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.changed_paths:
            raise ValueError("changed_paths cannot be empty")
        if not self.produced_artifacts:
            raise ValueError("produced_artifacts cannot be empty")
        if not self.verification_results:
            raise ValueError("verification_results cannot be empty")
        for result in self.verification_results:
            result.validate()
