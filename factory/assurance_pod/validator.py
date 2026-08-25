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
        required_acceptance_criterion_ids: tuple[str, ...] = (),
    ) -> AssuranceDecision:
        if not mission_id:
            raise ValueError("mission_id is required")
        if len(reports) != 3:
            raise ValueError("exactly three assurance reports are required")

        reviewers: list[str] = []
        report_ids: list[str] = []
        blocking: list[str] = []
        implementers = set(implementation_agent_ids)
        qa_report: AssuranceReport | None = None

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
            if report.reviewer_agent == "A10-QA":
                qa_report = report

        if set(reviewers) != ASSURANCE_ROLES:
            raise ValueError("assurance requires A09 Security, A10 QA and A12 Red Team")

        required = set(required_acceptance_criterion_ids)
        if len(required) != len(required_acceptance_criterion_ids):
            raise ValueError("required acceptance criterion IDs must be unique")
        if required:
            if qa_report is None:
                raise ValueError("A10-QA report is required for acceptance coverage")
            covered = {item.criterion_id for item in qa_report.acceptance_coverage}
            unknown = sorted(covered - required)
            if unknown:
                raise ValueError(f"A10-QA claimed unknown acceptance criteria:{','.join(unknown)}")
            for criterion_id in sorted(required - covered):
                blocking.append(f"QA-COVERAGE-{criterion_id}")

        decision = AssuranceDecision(
            mission_id=mission_id,
            status="CHANGES_REQUIRED" if blocking else "PASS",
            reviewer_agents=tuple(sorted(reviewers)),
            blocking_finding_ids=tuple(sorted(set(blocking))),
            report_ids=tuple(sorted(report_ids)),
        )
        decision.validate()
        return decision
