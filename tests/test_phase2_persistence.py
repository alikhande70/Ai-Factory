import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from factory.control_plane.graph import TaskNode
from factory.control_plane.state import TaskState
from factory.runtime.sqlite_store import SQLiteMissionStore


class PersistenceTests(unittest.TestCase):
    def test_restart_resume_preserves_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.db"
            nodes = (TaskNode("T1"), TaskNode("T2", ("T1",)))
            first = SQLiteMissionStore(path)
            runner = first.create_runner("M1", nodes)
            self.assertEqual(runner.release_ready_tasks(), ("T1",))
            runner.transition("T1", TaskState.IN_PROGRESS, actor_id="A02")
            runner.transition("T1", TaskState.READY_FOR_VERIFICATION, actor_id="A02")

            restarted = SQLiteMissionStore(path).restore_runner("M1")
            self.assertEqual(
                restarted.tasks["T1"].state, TaskState.READY_FOR_VERIFICATION
            )
            self.assertEqual(restarted.tasks["T2"].state, TaskState.BACKLOG)

            restarted.transition(
                "T1", TaskState.REVIEW, actor_id="A10", evidence_ids=("E1",)
            )
            restarted.transition(
                "T1",
                TaskState.VERIFIED,
                actor_id="A10",
                evidence_ids=("E1",),
                reviewer_ids=("A10",),
            )
            restarted.transition("T1", TaskState.DONE, actor_id="CONTROL-PLANE")
            self.assertEqual(restarted.release_ready_tasks(), ("T2",))
            self._finish(restarted, "T2", "A06", "A10")

            final = SQLiteMissionStore(path).restore_runner("M1")
            final.assert_all_done()
            final.ledger.verify_integrity()

    def test_tampered_persisted_event_is_rejected_on_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.db"
            store = SQLiteMissionStore(path)
            runner = store.create_runner("M1", (TaskNode("T1"),))
            runner.release_ready_tasks()
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "UPDATE audit_events SET payload_json = ? WHERE sequence = 1",
                    ('{"task_id":"T1","from":"BACKLOG","to":"DONE"}',),
                )
                connection.commit()
            with self.assertRaises(ValueError):
                SQLiteMissionStore(path).restore_runner("M1")

    def test_duplicate_mission_and_unknown_restore_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.db"
            store = SQLiteMissionStore(path)
            store.create_runner("M1", (TaskNode("T1"),))
            with self.assertRaises(ValueError):
                store.create_runner("M1", (TaskNode("T1"),))
            with self.assertRaises(KeyError):
                store.restore_runner("MISSING")

    def _finish(self, runner, task_id, worker, reviewer):
        runner.transition(task_id, TaskState.IN_PROGRESS, actor_id=worker)
        runner.transition(task_id, TaskState.READY_FOR_VERIFICATION, actor_id=worker)
        runner.transition(
            task_id,
            TaskState.REVIEW,
            actor_id=reviewer,
            evidence_ids=(f"E-{task_id}",),
        )
        runner.transition(
            task_id,
            TaskState.VERIFIED,
            actor_id=reviewer,
            evidence_ids=(f"E-{task_id}",),
            reviewer_ids=(reviewer,),
        )
        runner.transition(task_id, TaskState.DONE, actor_id="CONTROL-PLANE")


if __name__ == "__main__":
    unittest.main()
