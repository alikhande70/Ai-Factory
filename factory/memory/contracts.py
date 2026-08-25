from __future__ import annotations

from dataclasses import dataclass
import hashlib


MEMORY_CATEGORIES = frozenset({"LESSON", "PATTERN", "FAILURE", "DECISION"})
SOURCE_TRUST_LEVELS = frozenset({"CANONICAL", "VALIDATED_EXTERNAL", "UNTRUSTED_EXTERNAL"})
PROMOTION_STATUSES = frozenset({"APPROVED", "REJECTED"})


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    mission_id: str
    proposed_by: str
    category: str
    statement: str
    evidence_refs: tuple[str, ...]
    source_ref: str
    source_hash: str
    source_trust: str

    def validate(self) -> None:
        if not all(value.strip() for value in (self.candidate_id, self.mission_id, self.proposed_by, self.statement, self.source_ref, self.source_hash)):
            raise ValueError("memory candidate identity, statement and source provenance are required")
        if self.category not in MEMORY_CATEGORIES:
            raise ValueError(f"unknown memory category:{self.category}")
        if self.source_trust not in SOURCE_TRUST_LEVELS:
            raise ValueError(f"unknown source trust:{self.source_trust}")
        if not self.evidence_refs or any(not ref.strip() for ref in self.evidence_refs):
            raise ValueError("memory candidate requires evidence_refs")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("duplicate memory evidence_refs are not allowed")

    def fingerprint(self) -> str:
        self.validate()
        raw = "\n".join(
            (
                self.mission_id,
                self.category,
                self.statement,
                self.source_ref,
                self.source_hash,
                *sorted(self.evidence_refs),
            )
        )
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryPromotionDecision:
    candidate_id: str
    reviewer_id: str
    status: str
    reason: str
    verified_evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not all(value.strip() for value in (self.candidate_id, self.reviewer_id, self.reason)):
            raise ValueError("promotion decision identity, reviewer and reason are required")
        if self.status not in PROMOTION_STATUSES:
            raise ValueError(f"unknown promotion status:{self.status}")
        if self.status == "APPROVED" and not self.verified_evidence_refs:
            raise ValueError("approved memory promotion requires verified evidence")
        if len(self.verified_evidence_refs) != len(set(self.verified_evidence_refs)):
            raise ValueError("duplicate verified evidence refs are not allowed")


@dataclass(frozen=True)
class OrganizationalMemoryEntry:
    memory_id: str
    candidate_id: str
    mission_id: str
    category: str
    statement: str
    evidence_refs: tuple[str, ...]
    source_ref: str
    source_hash: str
    promoted_by: str
    fingerprint: str

    def validate(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.memory_id,
                self.candidate_id,
                self.mission_id,
                self.statement,
                self.source_ref,
                self.source_hash,
                self.promoted_by,
                self.fingerprint,
            )
        ):
            raise ValueError("organizational memory identity and provenance are required")
        if self.category not in MEMORY_CATEGORIES:
            raise ValueError(f"unknown memory category:{self.category}")
        if not self.evidence_refs:
            raise ValueError("organizational memory requires evidence_refs")
        if not self.fingerprint.startswith("sha256:"):
            raise ValueError("organizational memory fingerprint must be sha256")
