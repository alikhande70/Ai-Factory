from __future__ import annotations

from dataclasses import dataclass


ASSURANCE_ROLES = frozenset({"A09-SECURITY", "A10-QA", "A12-RED-TEAM"})
ASSURANCE_SEVERITIES = frozenset({"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"})


@dataclass(frozen=True)
class AssuranceFinding:
    finding_id: str
    category: str
    severity: str
    subject_ref: str
    statement: str
    evidence_refs: tuple[str, ...]
    remediation: str
    blocking: bool

    def validate(self) -> None:
        if not self.finding_id or not self.category.strip() or not self.subject_ref.strip():
            raise ValueError("finding_id, category and subject_ref are required")
        if self.severity not in ASSURANCE_SEVERITIES:
            raise ValueError(f"unknown assurance severity: {self.severity}")
        if not self.statement.strip() or not self.remediation.strip():
            raise ValueError("finding statement and remediation are required")
        if not self.evidence_refs:
            raise ValueError("assurance finding requires at least one evidence_ref")
        if self.severity in {"HIGH", "CRITICAL"} and not self.blocking:
            raise ValueError("HIGH/CRITICAL findings must be blocking")


@dataclass(frozen=True)
class AssuranceReport:
    report_id: str
    mission_id: str
    reviewer_agent: str
    subject_artifact_ref: str
    findings: tuple[AssuranceFinding, ...]
    verification_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.report_id or not self.mission_id or not self.subject_artifact_ref.strip():
            raise ValueError("report_id, mission_id and subject_artifact_ref are required")
        if self.reviewer_agent not in ASSURANCE_ROLES:
            raise ValueError(f"unknown assurance reviewer: {self.reviewer_agent}")
        if not self.verification_refs:
            raise ValueError("assurance report requires executable verification_refs")
        finding_ids = [item.finding_id for item in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("duplicate finding IDs are not allowed")
        for finding in self.findings:
            finding.validate()


@dataclass(frozen=True)
class AssuranceDecision:
    mission_id: str
    status: str
    reviewer_agents: tuple[str, ...]
    blocking_finding_ids: tuple[str, ...]
    report_ids: tuple[str, ...]

    def validate(self) -> None:
        if self.status not in {"PASS", "CHANGES_REQUIRED"}:
            raise ValueError("assurance status must be PASS or CHANGES_REQUIRED")
        if set(self.reviewer_agents) != ASSURANCE_ROLES:
            raise ValueError("assurance decision requires A09, A10 and A12")
        if len(self.report_ids) != 3 or len(set(self.report_ids)) != 3:
            raise ValueError("assurance decision requires three unique reports")
        if self.status == "PASS" and self.blocking_finding_ids:
            raise ValueError("PASS cannot contain blocking findings")
        if self.status == "CHANGES_REQUIRED" and not self.blocking_finding_ids:
            raise ValueError("CHANGES_REQUIRED needs at least one blocking finding")
