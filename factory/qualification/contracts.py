from __future__ import annotations

from dataclasses import dataclass


REQUIRED_DIMENSIONS = frozenset(
    {
        "MISSION_PLANNING",
        "ARCHITECTURE_UX",
        "FULL_STACK",
        "MIGRATION",
        "SECURITY",
        "QA_REGRESSION",
        "PARALLEL_ISOLATION",
        "RELIABILITY_RECONCILE",
        "APPROVAL_GATE",
        "PERSISTENCE_REPLAY",
        "MEMORY_PROMOTION",
    }
)


@dataclass(frozen=True)
class QualificationEvidence:
    dimension: str
    evidence_ref: str

    def validate(self) -> None:
        if self.dimension not in REQUIRED_DIMENSIONS:
            raise ValueError(f"unknown qualification dimension:{self.dimension}")
        if not self.evidence_ref.strip():
            raise ValueError("qualification evidence_ref required")


@dataclass(frozen=True)
class PathResult:
    path_id: str
    evidence: tuple[QualificationEvidence, ...]
    false_completion_rate: float
    quality: float
    cost_units: float
    latency_ms: float

    def validate(self) -> None:
        if not self.path_id.strip():
            raise ValueError("path_id required")
        if not 0 <= self.false_completion_rate <= 1:
            raise ValueError("false_completion_rate must be in [0,1]")
        if not 0 <= self.quality <= 1:
            raise ValueError("quality must be in [0,1]")
        if self.cost_units < 0 or self.latency_ms < 0:
            raise ValueError("cost/latency cannot be negative")
        for item in self.evidence:
            item.validate()
        if len({item.dimension for item in self.evidence}) != len(self.evidence):
            raise ValueError("duplicate qualification dimensions")

    def covered_dimensions(self) -> frozenset[str]:
        return frozenset(item.dimension for item in self.evidence)


@dataclass(frozen=True)
class QualificationComparison:
    factory: PathResult
    baseline: PathResult
    quality_delta: float
    false_completion_delta: float
    cost_overhead: float
    latency_overhead_ms: float
    factory_justified: bool
    rationale: str
