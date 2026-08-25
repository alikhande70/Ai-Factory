from __future__ import annotations

from .contracts import ASSURANCE_ROLES, AssuranceDecision, AssuranceReport


class AssuranceValidator:
    """Deterministic gate for independent Security, QA and Red-Team reports."""

    def decide(
        self,
        *,
        mission_id: str,
        reports: tuple[AssuranceReport, ...],
        implementation_agent_ids: tuple[str, ...],
    ) -> AssuranceDecision:
        if not mission_id:
            raise ValueError("mission_id is required")
        if len(reports) != 3:
            raise ValueError("exactly three assurance reports are required")

        reviewers: list[str] = []
        report_ids: list[str] = []
        blocking: list[str] = []
        implementers = set(implementation_agent_ids)

        for report in reports:
            report.validate()
            if report.mission_id != mission_id:
                raise ValueError("assurance report mission mismatch")
            if report.reviewer_agent in implementers:
                raise ValueError(f"reviewer independence violation:{report.reviewer_agent}")
            if report.reviewer_agent in reviewers:
                raise ValueError(f"duplicate assurance reviewer:{report.reviewer_agent}")
            if report.report_id in report_ids:
                raise ValueError(f"duplicate assurance report:{report.report_id}")
            reviewers.append(report.reviewer_agent)
            report_ids.append(report.report_id)
            blocking.extend(item.finding_id for item in report.findings if item.blocking)

        if set(reviewers) != ASSURANCE_ROLES:
            raise ValueError("assurance requires A09 Security, A10 QA and A12 Red Team")

        decision = AssuranceDecision(
            mission_id=mission_id,
            status="CHANGES_REQUIRED" if blocking else "PASS",
            reviewer_agents=tuple(sorted(reviewers)),
            blocking_finding_ids=tuple(sorted(blocking)),
            report_ids=tuple(sorted(report_ids)),
        )
        decision.validate()
        return decision
