from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import unittest

from factory.reliability.slo import (
    OperationSample,
    ServiceLevelObjective,
    evaluate_slo,
    remaining_error_budget,
)


class Phase11SLOTests(unittest.TestCase):
    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def setUp(self) -> None:
        self.objective = ServiceLevelObjective(
            objective_id="SLO-SEARCH-001",
            operation="canonical-search",
            max_p95_latency_ms=250.0,
            max_error_rate=0.01,
            min_throughput_per_second=20.0,
            min_samples=100,
        )

    def test_local_qualification_can_pass_but_cannot_claim_production(self) -> None:
        samples = tuple(OperationSample("canonical-search", float(50 + (index % 20)), True) for index in range(100))
        evidence = evaluate_slo(self.objective, samples, duration_seconds=4.0, environment="CI")
        self.assertTrue(evidence.qualified)
        self.assertEqual(evidence.claim_scope, "NON_PRODUCTION_QUALIFICATION_ONLY")
        with self.assertRaisesRegex(RuntimeError, "non_production_evidence_cannot_claim_production_slo"):
            evidence.assert_claimable_as_production()

    def test_insufficient_samples_fail_even_when_latency_is_good(self) -> None:
        samples = tuple(OperationSample("canonical-search", 1.0, True) for _ in range(10))
        evidence = evaluate_slo(self.objective, samples, duration_seconds=0.1, environment="CI")
        self.assertFalse(evidence.sufficient_samples)
        self.assertFalse(evidence.qualified)

    def test_p95_error_and_throughput_are_deterministic(self) -> None:
        samples = [OperationSample("canonical-search", float(index), True) for index in range(1, 101)]
        samples[-1] = OperationSample("canonical-search", 100.0, False)
        evidence = evaluate_slo(self.objective, samples, duration_seconds=5.0, environment="STAGING")
        self.assertEqual(evidence.p95_latency_ms, 95.0)
        self.assertEqual(evidence.error_rate, 0.01)
        self.assertEqual(evidence.throughput_per_second, 20.0)
        self.assertTrue(evidence.qualified)

    def test_sample_operation_mismatch_and_invalid_measurements_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "sample operation does not match objective"):
            evaluate_slo(
                self.objective,
                (OperationSample("other", 5.0, True),),
                duration_seconds=1.0,
                environment="LOCAL",
            )
        with self.assertRaises(ValueError):
            OperationSample("canonical-search", float("nan"), True)
        with self.assertRaises(ValueError):
            evaluate_slo(
                self.objective,
                (OperationSample("canonical-search", 1.0, True),),
                duration_seconds=0.0,
                environment="LOCAL",
            )

    def test_error_budget_is_explicit_and_can_go_negative(self) -> None:
        self.assertEqual(remaining_error_budget(self.objective, total_requests=1000, failed_requests=5), 5)
        self.assertEqual(remaining_error_budget(self.objective, total_requests=1000, failed_requests=12), -2)
        with self.assertRaises(ValueError):
            remaining_error_budget(self.objective, total_requests=10, failed_requests=11)

    def test_production_claim_requires_both_production_environment_and_qualified_evidence(self) -> None:
        passing = tuple(OperationSample("canonical-search", 20.0, True) for _ in range(100))
        production = evaluate_slo(self.objective, passing, duration_seconds=4.0, environment="PRODUCTION")
        production.assert_claimable_as_production()

        failing = tuple(OperationSample("canonical-search", 500.0, True) for _ in range(100))
        failed = evaluate_slo(self.objective, failing, duration_seconds=4.0, environment="PRODUCTION")
        with self.assertRaisesRegex(RuntimeError, "production_slo_not_qualified"):
            failed.assert_claimable_as_production()

    def test_slo_schema_matches_machine_readable_evidence_shape(self) -> None:
        schema = json.loads((self.repo_root / "schemas" / "slo-evidence.schema.json").read_text(encoding="utf-8"))
        samples = tuple(OperationSample("canonical-search", 20.0, True) for _ in range(100))
        evidence = evaluate_slo(self.objective, samples, duration_seconds=4.0, environment="CI")
        payload = asdict(evidence)
        self.assertEqual(set(payload), set(schema["required"]))
        self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
