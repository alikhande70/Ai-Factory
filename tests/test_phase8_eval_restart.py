from __future__ import annotations

import os
import tempfile
import unittest

from factory.evaluations import EvaluationBaseline, EvaluationCase, SQLiteEvaluationStore


class Phase8EvaluationRestartTests(unittest.TestCase):
    def test_baseline_integrity_survives_restart(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        try:
            baseline = EvaluationBaseline(
                baseline_id="CORE",
                version=1,
                created_by="A10",
                evaluator_id="A12",
                cases=(EvaluationCase("C1", "artifact://input", ("EV1",)),),
            )
            store = SQLiteEvaluationStore(path)
            store.register_baseline(baseline, actor_id="CONTROL-PLANE")
            store.close()

            store = SQLiteEvaluationStore(path)
            store.assert_baseline_integrity(baseline)
            store.close()
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
