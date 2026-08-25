from __future__ import annotations

from .contracts import MemoryCandidate, MemoryPromotionDecision, OrganizationalMemoryEntry


class MemoryPromotionGate:
    """Promotes reviewed lessons into organizational memory; never trusts raw input by default."""

    def promote(
        self,
        *,
        candidate: MemoryCandidate,
        decision: MemoryPromotionDecision,
        memory_id: str,
    ) -> OrganizationalMemoryEntry:
        candidate.validate()
        decision.validate()
        if decision.candidate_id != candidate.candidate_id:
            raise ValueError("promotion decision targets a different candidate")
        if decision.reviewer_id == candidate.proposed_by:
            raise ValueError("memory promotion requires an independent reviewer")
        if decision.status != "APPROVED":
            raise RuntimeError("rejected memory candidate cannot be promoted")
        if candidate.source_trust == "UNTRUSTED_EXTERNAL":
            raise RuntimeError("untrusted external source cannot be promoted directly")
        if not set(candidate.evidence_refs).issubset(set(decision.verified_evidence_refs)):
            raise ValueError("reviewer did not verify all candidate evidence")
        entry = OrganizationalMemoryEntry(
            memory_id=memory_id,
            candidate_id=candidate.candidate_id,
            mission_id=candidate.mission_id,
            category=candidate.category,
            statement=candidate.statement,
            evidence_refs=candidate.evidence_refs,
            source_ref=candidate.source_ref,
            source_hash=candidate.source_hash,
            promoted_by=decision.reviewer_id,
            fingerprint=candidate.fingerprint(),
        )
        entry.validate()
        return entry
