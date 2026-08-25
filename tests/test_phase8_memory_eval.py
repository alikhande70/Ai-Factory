from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from factory.evaluations import (
    CaseOutcome,
    EvaluationBaseline,
    EvaluationCase,
    SQLiteEvaluationStore,
    calculate_metrics,
)
from factory.memory import OrganizationalMemoryEntry, SQLiteOrganizationalMemoryStore


def memory_entry(memory_id: str, mission_id: str = "M-1", source_hash: str = "sha256:source") -> OrganizationalMemoryEntry:
    return OrganizationalMemoryEntry(
        memory_id=memory_id,
        candidate_id=f"C-{memory_id}",
        mission_id=mission_id,
        category="LESSON",
        statement=f"lesson {memory_id}",
        evidence_refs=("E-1",),
        source_ref="artifact://source/1",
        source_hash=source_hash,
        promoted_by="A12",
        fingerprint="sha256:" + "a" * 64,
    )


def baseline() -> EvaluationBaseline:
    return EvaluationBaseline(
        baseline_id="REGRESSION-CORE",
        version=1,
        created_by="A10-QA",
        evaluator_id="A12-EVAL",
        cases=(
            EvaluationCase("CASE-1", "artifact://input/1", ("EV-1",)),
            EvaluationCase("CASE-2", "artifact://input/2", ("EV-2",)),
        ),
    )


class Phase8MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.store = SQLiteOrganizationalMemoryStore(self.path)

    def tearDown(self) -> None:
        self.store.close()
        os.unlink(self.path)

    def test_promote_restart_recall_and_scope(self) -> None:
        entry = memory_entry("MEM-1")
        self.store.promote(entry, scope="MISSION", observed_source_hash=entry.source_hash)
        self.store.close()
        self.store = SQLiteOrganizationalMemoryStore(self.path)
        record = self.store.recall(
            "MEM-1", mission_id="M-1", observed_source_hashes={entry.source_ref: entry.source_hash}
        )
        self.assertEqual(record.status, "ACTIVE")
        self.assertTrue(self.store.verify_audit_chain())
        with self.assertRaises(PermissionError):
            self.store.recall(
                "MEM-1", mission_id="M-2", observed_source_hashes={entry.source_ref: entry.source_hash}
            )

    def test_source_hash_must_match_on_promotion_and_recall(self) -> None:
        entry = memory_entry("MEM-1")
        with self.assertRaises(RuntimeError):
            self.store.promote(entry, scope="GLOBAL", observed_source_hash="sha256:changed")
        self.store.promote(entry, scope="GLOBAL", observed_source_hash=entry.source_hash)
        with self.assertRaises(RuntimeError):
            self.store.recall(
                "MEM-1", mission_id="OTHER", observed_source_hashes={entry.source_ref: "sha256:changed"}
            )

    def test_supersession_is_append_only(self) -> None:
        first = memory_entry("MEM-1")
        second = memory_entry("MEM-2")
        self.store.promote(first, scope="GLOBAL", observed_source_hash=first.source_hash)
        self.store.promote(second, scope="GLOBAL", observed_source_hash=second.source_hash)
        self.store.supersede("MEM-1", "MEM-2")
        old = self.store.recall(
            "MEM-1", mission_id=None, observed_source_hashes={first.source_ref: first.source_hash}
        )
        self.assertEqual(old.status, "SUPERSEDED")
        self.assertEqual(old.superseded_by, "MEM-2")
        row = self.store._conn.execute("SELECT COUNT(*) AS n FROM memory_entries").fetchone()
        self.assertEqual(row["n"], 2)

    def test_audit_tampering_is_detected(self) -> None:
        entry = memory_entry("MEM-1")
        self.store.promote(entry, scope="GLOBAL", observed_source_hash=entry.source_hash)
        self.store._conn.execute("UPDATE memory_events SET payload='{}' WHERE seq=1")
        self.store._conn.commit()
        self.assertFalse(self.store.verify_audit_chain())


class Phase8EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.store = SQLiteEvaluationStore(self.path)

    def tearDown(self) -> None:
        self.store.close()
        os.unlink(self.path)

    def test_protected_baseline_requires_independent_registrar(self) -> None:
        b = baseline()
        with self.assertRaises(PermissionError):
            self.store.register_baseline(b, actor_id=b.created_by)
        fingerprint = self.store.register_baseline(b, actor_id="CONTROL-PLANE")
        self.assertEqual(fingerprint, b.fingerprint())

    def test_false_completion_quality_cost_latency_and_provider_summary(self) -> None:
        b = baseline()
        self.store.register_baseline(b, actor_id="CONTROL-PLANE")
        outcomes = (
            CaseOutcome("CASE-1", True, (), 0.8, 2.0, 100),
            CaseOutcome("CASE-2", True, ("EV-2",), 1.0, 3.0, 300),
        )
        metrics = calculate_metrics(b, outcomes)
        self.assertEqual(metrics.false_completion_rate, 0.5)
        self.assertAlmostEqual(metrics.mean_quality, 0.9)
        self.assertEqual(metrics.total_cost_units, 5.0)
        self.assertEqual(metrics.mean_latency_ms, 200.0)
        self.store.record_run(
            run_id="RUN-1",
            baseline=b,
            worker_id="WORKER-A",
            provider_id="PROVIDER-A",
            evaluator_actor_id="A12-EVAL",
            metrics=metrics,
        )
        summary = self.store.provider_summary()
        self.assertEqual(summary[0]["provider_id"], "PROVIDER-A")
        self.assertEqual(summary[0]["mean_false_completion_rate"], 0.5)

    def test_worker_cannot_evaluate_itself(self) -> None:
        b = baseline()
        self.store.register_baseline(b, actor_id="CONTROL-PLANE")
        metrics = calculate_metrics(
            b,
            (
                CaseOutcome("CASE-1", False, (), 0.5, 1.0, 10),
                CaseOutcome("CASE-2", False, (), 0.5, 1.0, 10),
            ),
        )
        with self.assertRaises(PermissionError):
            self.store.record_run(
                run_id="RUN-X",
                baseline=b,
                worker_id="A12-EVAL",
                provider_id="P",
                evaluator_actor_id="A12-EVAL",
                metrics=metrics,
            )

    def test_baseline_tamper_is_detected(self) -> None:
        b = baseline()
        self.store.register_baseline(b, actor_id="CONTROL-PLANE")
        mutated = EvaluationBaseline(
            baseline_id=b.baseline_id,
            version=b.version,
            created_by=b.created_by,
            evaluator_id=b.evaluator_id,
            cases=(EvaluationCase("CASE-1", "artifact://changed", ("EV-1",)), b.cases[1]),
        )
        with self.assertRaises(RuntimeError):
            self.store.assert_baseline_integrity(mutated)


if __name__ == "__main__":
    unittest.main()
