from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .contracts import (
    ClaimDisposition,
    EvidenceStance,
    ResearchBundle,
    SourceClass,
)


_HIGH_AUTHORITY = {
    SourceClass.PRIMARY_STANDARD,
    SourceClass.OFFICIAL_DOCUMENTATION,
    SourceClass.PEER_REVIEWED,
}


@dataclass(frozen=True)
class ResearchPolicy:
    min_independent_groups_for_critical: int = 2
    allow_single_normative_primary: bool = True
    require_contradiction_scan: bool = True
    max_unresolved_gaps_for_acceptance: int = 3

    def validate(self) -> None:
        if self.min_independent_groups_for_critical < 1:
            raise ValueError("critical evidence threshold must be positive")
        if self.max_unresolved_gaps_for_acceptance < 0:
            raise ValueError("gap threshold cannot be negative")


@dataclass(frozen=True)
class ResearchIssue:
    code: str
    message: str
    claim_id: str | None = None


@dataclass(frozen=True)
class ResearchAssessment:
    accepted: bool
    issues: tuple[ResearchIssue, ...]
    supported_claims: int
    contested_claims: int
    insufficient_claims: int
    source_count: int
    independent_group_count: int
    high_authority_source_count: int


class ResearchVerifier:
    """Deterministic evidence gate for Research Pod outputs.

    Research workers may discover and reason probabilistically, but they cannot
    promote their own conclusions into trusted organizational memory. This gate
    checks provenance, contradiction handling, freshness and evidence diversity.
    """

    def assess(
        self,
        bundle: ResearchBundle,
        *,
        policy: ResearchPolicy | None = None,
        now: datetime | None = None,
    ) -> ResearchAssessment:
        bundle.validate()
        policy = policy or ResearchPolicy()
        policy.validate()
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("assessment time must be timezone-aware")
        now = now.astimezone(timezone.utc)

        sources = {source.source_id: source for source in bundle.sources}
        issues: list[ResearchIssue] = []
        supported = contested = insufficient = 0

        for claim in bundle.claims:
            support_links = [link for link in claim.evidence if link.stance == EvidenceStance.SUPPORTS]
            contradict_links = [link for link in claim.evidence if link.stance == EvidenceStance.CONTRADICTS]
            support_sources = [sources[link.source_id] for link in support_links]
            groups = {source.independent_group for source in support_sources}
            high_authority = [source for source in support_sources if source.source_class in _HIGH_AUTHORITY]
            normative_primary = any(
                source.source_class == SourceClass.PRIMARY_STANDARD for source in support_sources
            )

            if claim.disposition == ClaimDisposition.SUPPORTED:
                supported += 1
                if not support_sources:
                    issues.append(
                        ResearchIssue(
                            "SUPPORTED_WITHOUT_SUPPORT",
                            "supported claim has no supporting evidence",
                            claim.claim_id,
                        )
                    )
                if contradict_links and policy.require_contradiction_scan:
                    issues.append(
                        ResearchIssue(
                            "CONTRADICTION_NOT_REFLECTED",
                            "claim is marked supported despite explicit contradictory evidence",
                            claim.claim_id,
                        )
                    )
                if claim.critical:
                    enough_groups = len(groups) >= policy.min_independent_groups_for_critical
                    primary_exception = policy.allow_single_normative_primary and normative_primary
                    if not (enough_groups or primary_exception):
                        issues.append(
                            ResearchIssue(
                                "CRITICAL_EVIDENCE_NOT_INDEPENDENT",
                                "critical claim lacks independent corroboration or a normative primary source",
                                claim.claim_id,
                            )
                        )
                    if not high_authority:
                        issues.append(
                            ResearchIssue(
                                "CRITICAL_CLAIM_LOW_AUTHORITY",
                                "critical claim has no high-authority supporting source",
                                claim.claim_id,
                            )
                        )
            elif claim.disposition == ClaimDisposition.CONTESTED:
                contested += 1
                if not support_links or not contradict_links:
                    issues.append(
                        ResearchIssue(
                            "CONTESTED_WITHOUT_BOTH_SIDES",
                            "contested claim must preserve supporting and contradictory evidence",
                            claim.claim_id,
                        )
                    )
            else:
                insufficient += 1
                if claim.confidence > 0.75:
                    issues.append(
                        ResearchIssue(
                            "INSUFFICIENT_OVERCONFIDENT",
                            "insufficient claim cannot carry high confidence",
                            claim.claim_id,
                        )
                    )

            if bundle.question.freshness_days is not None:
                threshold = now - timedelta(days=bundle.question.freshness_days)
                fresh_support = False
                for source in support_sources:
                    observed = _parse(source.retrieved_at)
                    published = _parse(source.published_at) if source.published_at is not None else observed
                    if max(observed, published) >= threshold:
                        fresh_support = True
                        break
                if claim.disposition == ClaimDisposition.SUPPORTED and not fresh_support:
                    issues.append(
                        ResearchIssue(
                            "FRESHNESS_REQUIREMENT_MISSED",
                            "supported claim lacks evidence inside the research freshness window",
                            claim.claim_id,
                        )
                    )

        if len(bundle.unresolved_gaps) > policy.max_unresolved_gaps_for_acceptance:
            issues.append(
                ResearchIssue(
                    "TOO_MANY_UNRESOLVED_GAPS",
                    "research bundle exceeds the unresolved-gap acceptance threshold",
                )
            )

        if bundle.question.critical and insufficient:
            issues.append(
                ResearchIssue(
                    "CRITICAL_QUESTION_HAS_INSUFFICIENT_CLAIMS",
                    "critical research question cannot pass with insufficient material claims",
                )
            )

        hard_codes = {
            "SUPPORTED_WITHOUT_SUPPORT",
            "CONTRADICTION_NOT_REFLECTED",
            "CRITICAL_EVIDENCE_NOT_INDEPENDENT",
            "CRITICAL_CLAIM_LOW_AUTHORITY",
            "CONTESTED_WITHOUT_BOTH_SIDES",
            "FRESHNESS_REQUIREMENT_MISSED",
            "TOO_MANY_UNRESOLVED_GAPS",
            "CRITICAL_QUESTION_HAS_INSUFFICIENT_CLAIMS",
        }
        accepted = not any(issue.code in hard_codes for issue in issues)
        return ResearchAssessment(
            accepted=accepted,
            issues=tuple(issues),
            supported_claims=supported,
            contested_claims=contested,
            insufficient_claims=insufficient,
            source_count=len(bundle.sources),
            independent_group_count=len({source.independent_group for source in bundle.sources}),
            high_authority_source_count=sum(
                source.source_class in _HIGH_AUTHORITY for source in bundle.sources
            ),
        )


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("research timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)
