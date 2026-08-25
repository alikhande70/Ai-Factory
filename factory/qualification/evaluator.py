from __future__ import annotations

from .contracts import PathResult, QualificationComparison, REQUIRED_DIMENSIONS


class QualificationEvaluator:
    """Compares Factory and simple paths without rewarding complexity for its own sake."""

    def compare(self, *, factory: PathResult, baseline: PathResult) -> QualificationComparison:
        factory.validate()
        baseline.validate()

        missing = REQUIRED_DIMENSIONS - factory.covered_dimensions()
        if missing:
            raise ValueError(f"factory qualification missing dimensions:{','.join(sorted(missing))}")

        quality_delta = factory.quality - baseline.quality
        false_completion_delta = baseline.false_completion_rate - factory.false_completion_rate
        cost_overhead = factory.cost_units - baseline.cost_units
        latency_overhead = factory.latency_ms - baseline.latency_ms

        # Factory is justified only when it produces a material safety/correctness gain.
        # Higher cost/latency are allowed, but complexity cannot win on feature-count alone.
        justified = (
            factory.false_completion_rate < baseline.false_completion_rate
            or quality_delta >= 0.10
        ) and factory.quality >= baseline.quality

        if justified:
            rationale = (
                "Factory path is justified by measurable quality/false-completion improvement; "
                "cost and latency overhead remain explicit routing inputs."
            )
        else:
            rationale = (
                "Factory complexity is not justified for this mission class; preserve the simpler/single-worker fast path."
            )

        return QualificationComparison(
            factory=factory,
            baseline=baseline,
            quality_delta=quality_delta,
            false_completion_delta=false_completion_delta,
            cost_overhead=cost_overhead,
            latency_overhead_ms=latency_overhead,
            factory_justified=justified,
            rationale=rationale,
        )
