from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json

from .inventory import SQLiteInventoryStore


class FindingSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class AnomalyFinding:
    finding_id: str
    anomaly_type: str
    severity: FindingSeverity
    canonical_id: str
    source_version_ids: tuple[str, ...]
    detector_id: str
    evidence_refs: tuple[str, ...]
    evidence_fingerprint: str
    summary: str
    observed_value: float
    threshold: float

    def validate(self) -> None:
        for name, value in (
            ("finding_id", self.finding_id),
            ("anomaly_type", self.anomaly_type),
            ("canonical_id", self.canonical_id),
            ("detector_id", self.detector_id),
            ("evidence_fingerprint", self.evidence_fingerprint),
            ("summary", self.summary),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        if not self.source_version_ids:
            raise ValueError("anomaly finding requires source versions")
        if not self.evidence_refs:
            raise ValueError("anomaly finding requires evidence references")
        if self.observed_value < 0.0 or self.threshold < 0.0:
            raise ValueError("finding numeric values must be non-negative")


class DuplicatePriceDivergenceDetector:
    """Deterministic source-price disagreement detector.

    It emits review evidence only. It never changes listing state, publisher trust,
    verification status or any other protected domain fact.
    """

    detector_id = "DET-DUPLICATE-PRICE-DIVERGENCE-V1"
    anomaly_type = "DUPLICATE_PRICE_DIVERGENCE"

    def __init__(
        self,
        *,
        medium_threshold: float = 0.20,
        high_threshold: float = 0.50,
        critical_threshold: float = 1.00,
    ) -> None:
        if not (0.0 < medium_threshold < high_threshold < critical_threshold):
            raise ValueError("detector thresholds must be positive and strictly increasing")
        self.medium_threshold = medium_threshold
        self.high_threshold = high_threshold
        self.critical_threshold = critical_threshold

    def detect(self, inventory: SQLiteInventoryStore, canonical_id: str) -> AnomalyFinding | None:
        members = inventory.source_members(canonical_id)
        latest_by_source: dict[tuple[str, str], dict[str, object]] = {}
        for member in members:
            key = (str(member["publisher_id"]), str(member["source_ref"]))
            prior = latest_by_source.get(key)
            if prior is None or str(member["last_verified_at"]) > str(prior["last_verified_at"]):
                latest_by_source[key] = member
        latest = tuple(latest_by_source.values())
        if len(latest) < 2:
            return None

        prices = [int(row["price_minor"]) for row in latest]
        minimum = min(prices)
        maximum = max(prices)
        relative_gap = float("inf") if minimum <= 0 else (maximum - minimum) / minimum
        if relative_gap < self.medium_threshold:
            return None

        if relative_gap >= self.critical_threshold:
            severity = FindingSeverity.CRITICAL
        elif relative_gap >= self.high_threshold:
            severity = FindingSeverity.HIGH
        else:
            severity = FindingSeverity.MEDIUM

        ordered = sorted(latest, key=lambda row: str(row["source_version_id"]))
        source_ids = tuple(str(row["source_version_id"]) for row in ordered)
        evidence_payload = [
            {
                "source_version_id": str(row["source_version_id"]),
                "publisher_id": str(row["publisher_id"]),
                "source_ref": str(row["source_ref"]),
                "price_minor": int(row["price_minor"]),
                "last_verified_at": str(row["last_verified_at"]),
            }
            for row in ordered
        ]
        canonical_payload = json.dumps(evidence_payload, sort_keys=True, separators=(",", ":"))
        evidence_fingerprint = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        finding_digest = hashlib.sha256(
            f"{self.detector_id}|{canonical_id}|{evidence_fingerprint}".encode("utf-8")
        ).hexdigest()[:24]
        observed = relative_gap if relative_gap != float("inf") else 999999.0
        finding = AnomalyFinding(
            finding_id=f"FIND-{finding_digest}",
            anomaly_type=self.anomaly_type,
            severity=severity,
            canonical_id=canonical_id,
            source_version_ids=source_ids,
            detector_id=self.detector_id,
            evidence_refs=tuple(f"SOURCE:{source_id}" for source_id in source_ids),
            evidence_fingerprint=evidence_fingerprint,
            summary="Independent current source records disagree materially on price; operator review required.",
            observed_value=round(observed, 6),
            threshold=self.medium_threshold,
        )
        finding.validate()
        return finding
