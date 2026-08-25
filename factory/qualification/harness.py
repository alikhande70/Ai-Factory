from __future__ import annotations

from time import perf_counter
from typing import Callable

from .contracts import PathResult, QualificationEvidence, REQUIRED_DIMENSIONS


class QualificationHarness:
    """Builds comparison results from observed evidence instead of hand-scored outcomes."""

    def run_path(
        self,
        *,
        path_id: str,
        action: Callable[[], tuple[QualificationEvidence, ...]],
        claimed_complete: bool,
    ) -> PathResult:
        started = perf_counter()
        evidence = action()
        latency_ms = (perf_counter() - started) * 1000.0
        covered = frozenset(item.dimension for item in evidence)
        quality = len(covered & REQUIRED_DIMENSIONS) / len(REQUIRED_DIMENSIONS)
        false_completion = 1.0 if claimed_complete and not REQUIRED_DIMENSIONS.issubset(covered) else 0.0
        # Cost unit is a controlled proxy: one unit per independently produced qualification evidence item.
        # It is intentionally not presented as provider billing cost.
        cost_units = float(len(evidence))
        return PathResult(
            path_id=path_id,
            evidence=evidence,
            false_completion_rate=false_completion,
            quality=quality,
            cost_units=cost_units,
            latency_ms=latency_ms,
        )
