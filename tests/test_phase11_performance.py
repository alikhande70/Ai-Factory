from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from factory.reliability.performance import qualify_operation, write_report
from factory.reliability.slo import ServiceLevelObjective
from factory.runtime.catalog import SQLiteRuntimeCatalog


class Phase11PerformanceQualificationTests(unittest.TestCase):
    def test_runtime_catalog_read_path_meets_broad_ci_regression_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "runtime.db"
            catalog = SQLiteRuntimeCatalog(db)
            catalog.add_artifact(
                mission_id="MISSION-PERF",
                artifact_id="ART-1",
                content="stable payload",
                created_by="A11",
            )
            objective = ServiceLevelObjective(
                objective_id="SLO-CATALOG-READ-CI",
                operation="runtime-catalog-latest-artifact",
                max_p95_latency_ms=100.0,
                max_error_rate=0.0,
                min_throughput_per_second=5.0,
                min_samples=100,
            )
            report = qualify_operation(
                objective=objective,
                iterations=100,
                operation=lambda: catalog.latest_artifact("MISSION-PERF", "ART-1"),
                environment="CI",
                warmup_iterations=5,
            )

            self.assertTrue(report.evidence.qualified)
            self.assertEqual(report.evidence.claim_scope, "NON_PRODUCTION_QUALIFICATION_ONLY")
            self.assertEqual(report.evidence.sample_count, 100)
            self.assertRegex(report.environment_fingerprint_sha256, r"^[0-9a-f]{64}$")

    def test_operation_failures_are_counted_not_hidden(self) -> None:
        counter = {"n": 0}

        def flaky() -> None:
            counter["n"] += 1
            if counter["n"] % 2 == 0:
                raise RuntimeError("synthetic failure")

        objective = ServiceLevelObjective(
            objective_id="SLO-FLAKY",
            operation="flaky-op",
            max_p95_latency_ms=1000.0,
            max_error_rate=0.10,
            min_throughput_per_second=0.0,
            min_samples=10,
        )
        report = qualify_operation(
            objective=objective,
            iterations=10,
            operation=flaky,
            environment="LOCAL",
            warmup_iterations=0,
        )
        self.assertEqual(report.evidence.error_rate, 0.5)
        self.assertFalse(report.evidence.qualified)

    def test_report_persistence_is_explicit_and_non_overwriting(self) -> None:
        objective = ServiceLevelObjective(
            objective_id="SLO-NOOP",
            operation="noop",
            max_p95_latency_ms=1000.0,
            max_error_rate=0.0,
            min_throughput_per_second=0.0,
            min_samples=2,
        )
        report = qualify_operation(
            objective=objective,
            iterations=2,
            operation=lambda: None,
            environment="LOCAL",
            warmup_iterations=0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            write_report(report, path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["evidence"]["claim_scope"], "NON_PRODUCTION_QUALIFICATION_ONLY")
            self.assertEqual(payload["report_version"], 1)
            with self.assertRaises(FileExistsError):
                write_report(report, path)


if __name__ == "__main__":
    unittest.main()
