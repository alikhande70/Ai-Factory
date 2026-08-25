from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    input_ref: str
    expected_evidence_refs: tuple[str, ...]
    protected: bool = True

    def validate(self) -> None:
        if not self.case_id.strip() or not self.input_ref.strip():
            raise ValueError("evaluation case identity and input_ref are required")
        if not self.expected_evidence_refs or any(not ref.strip() for ref in self.expected_evidence_refs):
            raise ValueError("evaluation case requires expected evidence refs")
        if len(self.expected_evidence_refs) != len(set(self.expected_evidence_refs)):
            raise ValueError("duplicate expected evidence refs")


@dataclass(frozen=True)
class EvaluationBaseline:
    baseline_id: str
    version: int
    created_by: str
    evaluator_id: str
    cases: tuple[EvaluationCase, ...]

    def validate(self) -> None:
        if not all(v.strip() for v in (self.baseline_id, self.created_by, self.evaluator_id)):
            raise ValueError("baseline identity is required")
        if self.version < 1 or not self.cases:
            raise ValueError("baseline requires positive version and cases")
        for case in self.cases:
            case.validate()
        if len({c.case_id for c in self.cases}) != len(self.cases):
            raise ValueError("duplicate evaluation case ids")

    def fingerprint(self) -> str:
        self.validate()
        payload = {
            "baseline_id": self.baseline_id,
            "version": self.version,
            "created_by": self.created_by,
            "evaluator_id": self.evaluator_id,
            "cases": [
                {
                    "case_id": c.case_id,
                    "input_ref": c.input_ref,
                    "expected_evidence_refs": sorted(c.expected_evidence_refs),
                    "protected": c.protected,
                }
                for c in self.cases
            ],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    claimed_complete: bool
    evidence_refs: tuple[str, ...]
    quality_score: float
    cost_units: float
    latency_ms: int

    def validate(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case id required")
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("quality_score must be in [0,1]")
        if self.cost_units < 0 or self.latency_ms < 0:
            raise ValueError("cost and latency cannot be negative")


@dataclass(frozen=True)
class EvaluationMetrics:
    case_count: int
    false_completion_rate: float
    mean_quality: float
    total_cost_units: float
    mean_latency_ms: float


def calculate_metrics(baseline: EvaluationBaseline, outcomes: tuple[CaseOutcome, ...]) -> EvaluationMetrics:
    baseline.validate()
    if len(outcomes) != len(baseline.cases):
        raise ValueError("outcomes must cover baseline exactly")
    expected = {c.case_id: set(c.expected_evidence_refs) for c in baseline.cases}
    seen: set[str] = set()
    false_completions = 0
    quality = 0.0
    cost = 0.0
    latency = 0
    for outcome in outcomes:
        outcome.validate()
        if outcome.case_id not in expected or outcome.case_id in seen:
            raise ValueError("unknown or duplicate outcome case")
        seen.add(outcome.case_id)
        evidence_ok = expected[outcome.case_id].issubset(set(outcome.evidence_refs))
        if outcome.claimed_complete and not evidence_ok:
            false_completions += 1
        quality += outcome.quality_score
        cost += outcome.cost_units
        latency += outcome.latency_ms
    count = len(outcomes)
    return EvaluationMetrics(
        case_count=count,
        false_completion_rate=false_completions / count,
        mean_quality=quality / count,
        total_cost_units=cost,
        mean_latency_ms=latency / count,
    )
