from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3

from factory.runtime.secrets import secret_safe_projection

from .contracts import EvaluationBaseline, EvaluationMetrics


class SQLiteEvaluationStore:
    """Persists immutable baseline versions and evaluation summaries."""

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS eval_baselines(
                baseline_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                fingerprint TEXT NOT NULL UNIQUE,
                evaluator_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY(baseline_id, version)
            );
            CREATE TABLE IF NOT EXISTS eval_runs(
                run_id TEXT PRIMARY KEY,
                baseline_id TEXT NOT NULL,
                baseline_version INTEGER NOT NULL,
                baseline_fingerprint TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                metrics TEXT NOT NULL,
                FOREIGN KEY(baseline_id,baseline_version) REFERENCES eval_baselines(baseline_id,version)
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _dump(value: object) -> str:
        return json.dumps(secret_safe_projection(value), sort_keys=True, separators=(",", ":"))

    def register_baseline(self, baseline: EvaluationBaseline, *, actor_id: str) -> str:
        baseline.validate()
        if actor_id == baseline.evaluator_id:
            # Creation and evaluation authority must not collapse into one mutable principal.
            raise PermissionError("evaluator cannot self-register its protected baseline")
        if any(case.protected for case in baseline.cases) and actor_id == baseline.created_by:
            raise PermissionError("baseline author requires independent registrar for protected cases")
        fingerprint = baseline.fingerprint()
        payload = {
            "baseline_id": baseline.baseline_id,
            "version": baseline.version,
            "created_by": baseline.created_by,
            "evaluator_id": baseline.evaluator_id,
            "cases": [asdict(case) for case in baseline.cases],
        }
        with self._conn:
            self._conn.execute(
                "INSERT INTO eval_baselines(baseline_id,version,fingerprint,evaluator_id,payload) VALUES(?,?,?,?,?)",
                (baseline.baseline_id, baseline.version, fingerprint, baseline.evaluator_id, self._dump(payload)),
            )
        return fingerprint

    def assert_baseline_integrity(self, baseline: EvaluationBaseline) -> None:
        row = self._conn.execute(
            "SELECT fingerprint FROM eval_baselines WHERE baseline_id=? AND version=?",
            (baseline.baseline_id, baseline.version),
        ).fetchone()
        if row is None:
            raise KeyError((baseline.baseline_id, baseline.version))
        if row["fingerprint"] != baseline.fingerprint():
            raise RuntimeError("protected evaluation baseline changed after registration")

    def record_run(
        self,
        *,
        run_id: str,
        baseline: EvaluationBaseline,
        worker_id: str,
        provider_id: str,
        evaluator_actor_id: str,
        metrics: EvaluationMetrics,
    ) -> None:
        if not all(v.strip() for v in (run_id, worker_id, provider_id, evaluator_actor_id)):
            raise ValueError("evaluation run identity is required")
        if worker_id == evaluator_actor_id:
            raise PermissionError("evaluated worker cannot act as its evaluator")
        if baseline.evaluator_id != evaluator_actor_id:
            raise PermissionError("evaluation actor does not own this baseline evaluator role")
        self.assert_baseline_integrity(baseline)
        with self._conn:
            self._conn.execute(
                "INSERT INTO eval_runs(run_id,baseline_id,baseline_version,baseline_fingerprint,worker_id,provider_id,metrics) VALUES(?,?,?,?,?,?,?)",
                (
                    run_id,
                    baseline.baseline_id,
                    baseline.version,
                    baseline.fingerprint(),
                    worker_id,
                    provider_id,
                    self._dump(asdict(metrics)),
                ),
            )

    def provider_summary(self) -> list[dict[str, object]]:
        rows = self._conn.execute("SELECT provider_id,metrics FROM eval_runs ORDER BY run_id").fetchall()
        grouped: dict[str, list[dict[str, float]]] = {}
        for row in rows:
            grouped.setdefault(row["provider_id"], []).append(json.loads(row["metrics"]))
        result: list[dict[str, object]] = []
        for provider, items in sorted(grouped.items()):
            n = len(items)
            result.append(
                {
                    "provider_id": provider,
                    "runs": n,
                    "mean_quality": sum(x["mean_quality"] for x in items) / n,
                    "mean_false_completion_rate": sum(x["false_completion_rate"] for x in items) / n,
                    "mean_cost_units": sum(x["total_cost_units"] for x in items) / n,
                    "mean_latency_ms": sum(x["mean_latency_ms"] for x in items) / n,
                }
            )
        return result
