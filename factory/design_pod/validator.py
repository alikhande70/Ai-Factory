from __future__ import annotations

from dataclasses import dataclass

from .contracts import DesignBundle


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    severity: str
    message: str
    subject_id: str | None = None


class DesignBundleValidator:
    """Deterministic checks for cross-role Design Pod output.

    LLM workers may propose requirements, architecture and UX. This validator
    enforces traceability and minimum consistency before those artifacts can
    become canonical build inputs.
    """

    def validate(self, bundle: DesignBundle) -> tuple[ValidationFinding, ...]:
        bundle.validate()
        findings: list[ValidationFinding] = []

        requirement_ids = [item.requirement_id for item in bundle.requirements]
        requirement_set = set(requirement_ids)
        if len(requirement_ids) != len(requirement_set):
            findings.append(ValidationFinding("DUPLICATE_REQUIREMENT_ID", "BLOCKING", "requirement IDs must be unique"))

        criterion_ids = [item.criterion_id for item in bundle.acceptance_criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            findings.append(ValidationFinding("DUPLICATE_CRITERION_ID", "BLOCKING", "acceptance criterion IDs must be unique"))

        covered_by_acceptance: set[str] = set()
        for criterion in bundle.acceptance_criteria:
            if criterion.requirement_id not in requirement_set:
                findings.append(
                    ValidationFinding(
                        "ORPHAN_ACCEPTANCE_CRITERION",
                        "BLOCKING",
                        f"criterion references unknown requirement {criterion.requirement_id}",
                        criterion.criterion_id,
                    )
                )
            else:
                covered_by_acceptance.add(criterion.requirement_id)

        for requirement in bundle.requirements:
            if requirement.priority == "MUST" and requirement.requirement_id not in covered_by_acceptance:
                findings.append(
                    ValidationFinding(
                        "MUST_WITHOUT_ACCEPTANCE_CRITERION",
                        "BLOCKING",
                        "MUST requirement has no executable acceptance criterion",
                        requirement.requirement_id,
                    )
                )

        for decision in bundle.architecture_decisions:
            for requirement_id in decision.requirement_ids:
                if requirement_id not in requirement_set:
                    findings.append(
                        ValidationFinding(
                            "ARCHITECTURE_UNKNOWN_REQUIREMENT",
                            "BLOCKING",
                            f"architecture decision references unknown requirement {requirement_id}",
                            decision.decision_id,
                        )
                    )

        for flow in bundle.ux_flows:
            for requirement_id in flow.requirement_ids:
                if requirement_id not in requirement_set:
                    findings.append(
                        ValidationFinding(
                            "UX_UNKNOWN_REQUIREMENT",
                            "BLOCKING",
                            f"UX flow references unknown requirement {requirement_id}",
                            flow.flow_id,
                        )
                    )

        must_ids = {item.requirement_id for item in bundle.requirements if item.priority == "MUST"}
        design_covered = {
            requirement_id
            for decision in bundle.architecture_decisions
            for requirement_id in decision.requirement_ids
        } | {
            requirement_id
            for flow in bundle.ux_flows
            for requirement_id in flow.requirement_ids
        }
        for requirement_id in sorted(must_ids - design_covered):
            findings.append(
                ValidationFinding(
                    "MUST_WITHOUT_DESIGN_COVERAGE",
                    "BLOCKING",
                    "MUST requirement is not covered by architecture or UX",
                    requirement_id,
                )
            )

        if not bundle.risks:
            findings.append(ValidationFinding("NO_RISKS_RECORDED", "WARNING", "design bundle records no material risks"))

        return tuple(findings)

    def is_build_ready(self, bundle: DesignBundle) -> bool:
        return not any(item.severity == "BLOCKING" for item in self.validate(bundle))
