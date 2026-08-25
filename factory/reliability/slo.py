from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Literal


Environment = Literal["LOCAL", "CI", "STAGING", "PRODUCTION"]


@dataclass(frozen=True)
class ServiceLevelObjective:
    objective_id: str
    operation: str
    max_p95_latency_ms: float
    max_error_rate: float
    min_throughput_per_second: float
    min_samples: int

    def __post_init__(self) -> None:
        if not self.objective_id.strip() or not self.operation.strip():
            raise ValueError("objective_id and operation are required")
        if self.max_p95_latency_ms <= 0:
            raise ValueError("max_p95_latency_ms must be > 0")
        if not 0 <= self.max_error_rate <= 1:
            raise ValueError("max_error_rate must be between 0 and 1")
        if self.min_throughput_per_second < 0:
            raise ValueError("min_throughput_per_second must be >= 0")
        if self.min_samples < 1:
            raise ValueError("min_samples must be >= 1")


@dataclass(frozen=True)
class OperationSample:
    operation: str
    latency_ms: float
    success: bool

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("sample operation is required")
        if not math.isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("latency_ms must be finite and >= 0")


@dataclass(frozen=True)
class SLOEvidence:
    objective_id: str
    operation: str
    environment: Environment
    sample_count: int
    duration_seconds: float
    p95_latency_ms: float
    error_rate: float
    throughput_per_second: float
    latency_pass: bool
    error_rate_pass: bool
    throughput_pass: bool
    sufficient_samples: bool
    qualified: bool
    claim_scope: str

    def assert_claimable_as_production(self) -> None:
        if self.environment != "PRODUCTION":
            raise RuntimeError("non_production_evidence_cannot_claim_production_slo")
        if not self.qualified:
            raise RuntimeError("production_slo_not_qualified")


def _nearest_rank_percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0,1]")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def evaluate_slo(
    objective: ServiceLevelObjective,
    samples: Iterable[OperationSample],
    *,
    duration_seconds: float,
    environment: Environment,
) -> SLOEvidence:
    if environment not in {"LOCAL", "CI", "STAGING", "PRODUCTION"}:
        raise ValueError("unsupported environment")
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("duration_seconds must be finite and > 0")

    selected = tuple(samples)
    if not selected:
        raise ValueError("at least one sample is required")
    if any(sample.operation != objective.operation for sample in selected):
        raise ValueError("sample operation does not match objective")

    sample_count = len(selected)
    p95 = _nearest_rank_percentile([sample.latency_ms for sample in selected], 0.95)
    failures = sum(1 for sample in selected if not sample.success)
    error_rate = failures / sample_count
    throughput = sample_count / duration_seconds
    sufficient = sample_count >= objective.min_samples
    latency_pass = p95 <= objective.max_p95_latency_ms
    error_pass = error_rate <= objective.max_error_rate
    throughput_pass = throughput >= objective.min_throughput_per_second
    qualified = sufficient and latency_pass and error_pass and throughput_pass

    claim_scope = "PRODUCTION_SLO_EVIDENCE" if environment == "PRODUCTION" else "NON_PRODUCTION_QUALIFICATION_ONLY"
    return SLOEvidence(
        objective_id=objective.objective_id,
        operation=objective.operation,
        environment=environment,
        sample_count=sample_count,
        duration_seconds=duration_seconds,
        p95_latency_ms=p95,
        error_rate=error_rate,
        throughput_per_second=throughput,
        latency_pass=latency_pass,
        error_rate_pass=error_pass,
        throughput_pass=throughput_pass,
        sufficient_samples=sufficient,
        qualified=qualified,
        claim_scope=claim_scope,
    )


def remaining_error_budget(objective: ServiceLevelObjective, *, total_requests: int, failed_requests: int) -> int:
    if total_requests < 0 or failed_requests < 0 or failed_requests > total_requests:
        raise ValueError("invalid request counts")
    allowed_failures = math.floor(total_requests * objective.max_error_rate)
    return allowed_failures - failed_requests
