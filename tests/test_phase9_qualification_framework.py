from __future__ import annotations

import unittest

from factory.qualification import (
    PathResult,
    QualificationEvidence,
    QualificationEvaluator,
    REQUIRED_DIMENSIONS,
)


def evidence_all() -> tuple[QualificationEvidence, ...]:
    return tuple(
        QualificationEvidence(dimension, f"test://phase9/{dimension.lower()}")
        for dimension in sorted(REQUIRED_DIMENSIONS)
    )


class Phase9QualificationFrameworkTests(unittest.TestCase):
    def test_factory_cannot_be_qualified_with_missing_dimension(self) -> None:
        partial = evidence_all()[:-1]
        factory = PathResult("FACTORY", partial, 0.0, 0.95, 20.0, 500.0)
        baseline = PathResult("SIMPLE", (), 0.2, 0.75, 5.0, 100.0)
        with self.assertRaisesRegex(ValueError, "missing dimensions"):
            QualificationEvaluator().compare(factory=factory, baseline=baseline)

    def test_factory_complexity_is_justified_by_measurable_safety_gain(self) -> None:
        factory = PathResult("FACTORY", evidence_all(), 0.0, 0.92, 20.0, 500.0)
        baseline = PathResult("SIMPLE", (), 0.25, 0.82, 5.0, 100.0)
        comparison = QualificationEvaluator().compare(factory=factory, baseline=baseline)
        self.assertTrue(comparison.factory_justified)
        self.assertAlmostEqual(comparison.quality_delta, 0.10)
        self.assertAlmostEqual(comparison.false_completion_delta, 0.25)
        self.assertEqual(comparison.cost_overhead, 15.0)
        self.assertEqual(comparison.latency_overhead_ms, 400.0)

    def test_more_complex_factory_does_not_win_without_outcome_gain(self) -> None:
        factory = PathResult("FACTORY", evidence_all(), 0.1, 0.80, 20.0, 500.0)
        baseline = PathResult("SIMPLE", (), 0.1, 0.82, 5.0, 100.0)
        comparison = QualificationEvaluator().compare(factory=factory, baseline=baseline)
        self.assertFalse(comparison.factory_justified)
        self.assertIn("single-worker fast path", comparison.rationale)


if __name__ == "__main__":
    unittest.main()
