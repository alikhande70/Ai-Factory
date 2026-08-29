from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from urllib.parse import urlparse


class SourceClass(str, Enum):
    PRIMARY_STANDARD = "PRIMARY_STANDARD"
    OFFICIAL_DOCUMENTATION = "OFFICIAL_DOCUMENTATION"
    PEER_REVIEWED = "PEER_REVIEWED"
    PREPRINT = "PREPRINT"
    VENDOR_DOCUMENTATION = "VENDOR_DOCUMENTATION"
    SECONDARY = "SECONDARY"
    COMMUNITY = "COMMUNITY"


class EvidenceStance(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CONTEXT_ONLY = "CONTEXT_ONLY"


class ClaimDisposition(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class ResearchQuestion:
    question_id: str
    text: str
    critical: bool = False
    freshness_days: int | None = None

    def validate(self) -> None:
        if not self.question_id.strip() or not self.text.strip():
            raise ValueError("research question id and text are required")
        if self.freshness_days is not None and self.freshness_days < 0:
            raise ValueError("freshness_days cannot be negative")


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    uri: str
    title: str
    publisher: str
    source_class: SourceClass
    independent_group: str
    retrieved_at: str
    content_hash: str
    published_at: str | None = None

    def validate(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.source_id,
                self.uri,
                self.title,
                self.publisher,
                self.independent_group,
                self.retrieved_at,
                self.content_hash,
            )
        ):
            raise ValueError("source identity, provenance and content hash are required")
        parsed = urlparse(self.uri)
        if parsed.scheme not in {"https", "http", "repo"}:
            raise ValueError("source uri must use http(s) or repo scheme")
        _parse_aware_iso8601(self.retrieved_at, "retrieved_at")
        if self.published_at is not None:
            _parse_aware_iso8601(self.published_at, "published_at")
        if not self.content_hash.startswith("sha256:") or len(self.content_hash) != 71:
            raise ValueError("content_hash must be a sha256:<64 hex> fingerprint")
        try:
            int(self.content_hash.removeprefix("sha256:"), 16)
        except ValueError as exc:
            raise ValueError("content_hash must contain hexadecimal sha256 data") from exc


@dataclass(frozen=True)
class EvidenceLink:
    source_id: str
    stance: EvidenceStance
    evidence_ref: str

    def validate(self) -> None:
        if not self.source_id.strip() or not self.evidence_ref.strip():
            raise ValueError("evidence source and evidence_ref are required")


@dataclass(frozen=True)
class ResearchClaim:
    claim_id: str
    statement: str
    evidence: tuple[EvidenceLink, ...]
    disposition: ClaimDisposition
    confidence: float
    critical: bool = False

    def validate(self) -> None:
        if not self.claim_id.strip() or not self.statement.strip():
            raise ValueError("claim identity and statement are required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("claim confidence must be in [0,1]")
        if not self.evidence:
            raise ValueError("claims require explicit evidence links")
        for link in self.evidence:
            link.validate()


@dataclass(frozen=True)
class ResearchBundle:
    bundle_id: str
    question: ResearchQuestion
    sources: tuple[SourceRecord, ...]
    claims: tuple[ResearchClaim, ...]
    conclusion: str
    unresolved_gaps: tuple[str, ...]
    participating_agents: tuple[str, ...]
    created_at: str

    def validate(self) -> None:
        if not self.bundle_id.strip() or not self.conclusion.strip():
            raise ValueError("bundle identity and conclusion are required")
        self.question.validate()
        if not self.sources or not self.claims:
            raise ValueError("research bundle requires sources and claims")
        if len(self.participating_agents) < 2:
            raise ValueError("research bundle must record at least two participating roles")
        if len(set(self.participating_agents)) != len(self.participating_agents):
            raise ValueError("duplicate participating agent roles")
        _parse_aware_iso8601(self.created_at, "created_at")

        source_ids: set[str] = set()
        for source in self.sources:
            source.validate()
            if source.source_id in source_ids:
                raise ValueError("duplicate source id")
            source_ids.add(source.source_id)

        claim_ids: set[str] = set()
        for claim in self.claims:
            claim.validate()
            if claim.claim_id in claim_ids:
                raise ValueError("duplicate claim id")
            claim_ids.add(claim.claim_id)
            for link in claim.evidence:
                if link.source_id not in source_ids:
                    raise ValueError("claim references an unknown source")

    def fingerprint(self) -> str:
        self.validate()
        payload = {
            "bundle_id": self.bundle_id,
            "question": {
                "question_id": self.question.question_id,
                "text": self.question.text,
                "critical": self.question.critical,
                "freshness_days": self.question.freshness_days,
            },
            "sources": [
                {
                    "source_id": s.source_id,
                    "uri": s.uri,
                    "title": s.title,
                    "publisher": s.publisher,
                    "source_class": s.source_class.value,
                    "independent_group": s.independent_group,
                    "retrieved_at": s.retrieved_at,
                    "published_at": s.published_at,
                    "content_hash": s.content_hash,
                }
                for s in sorted(self.sources, key=lambda item: item.source_id)
            ],
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "statement": c.statement,
                    "disposition": c.disposition.value,
                    "confidence": c.confidence,
                    "critical": c.critical,
                    "evidence": [
                        {
                            "source_id": e.source_id,
                            "stance": e.stance.value,
                            "evidence_ref": e.evidence_ref,
                        }
                        for e in sorted(c.evidence, key=lambda item: (item.source_id, item.evidence_ref))
                    ],
                }
                for c in sorted(self.claims, key=lambda item: item.claim_id)
            ],
            "conclusion": self.conclusion,
            "unresolved_gaps": sorted(self.unresolved_gaps),
            "participating_agents": sorted(self.participating_agents),
            "created_at": self.created_at,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_aware_iso8601(value: str, field: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)
