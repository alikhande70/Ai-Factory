import unittest

from factory.control_plane.contracts import (
    EvidenceKind,
    EvidenceRecord,
    ObjectionRecord,
    ObjectionSeverity,
    ReviewRecord,
)
from factory.control_plane.graph import TaskNode
from factory.control_plane.runner import MissionRunner
from factory.control_plane.state import TaskState


class ContractTests(unittest.TestCase):
    def test_review_independence(self):
        review = ReviewRecord("R1", "M1", "T1", "A05", ("E1",), "APPROVE")
        with self.assertRaises(ValueError):
            review.validate(("A05",))

    def test_typed_records_validate(self):
        EvidenceRecord(
            "E1", "M1", "T1", "A10", EvidenceKind.TEST, "tests pass"
        ).validate()
        ObjectionRecord(
            "O1", "M1", "T1", "A09", ObjectionSeverity.BLOCKING, "auth flaw"
        ).validate()


class GraphExecutionTests(unittest.TestCase):
    def test_dependency_release_and_replay(self):
        nodes = (
            TaskNode("T1", (), ("product/",)),
            TaskNode("T2", ("T1",), ("backend/",)),
            TaskNode("T3", ("T1",), ("frontend/",)),
        )
        runner = MissionRunner("M1", ["T1", "T2", "T3"], task_nodes=nodes)

        self.assertEqual(runner.release_ready_tasks(), ("T1",))
        self._finish(runner, "T1", "A02", "A10")
        self.assertEqual(runner.release_ready_tasks(), ("T2", "T3"))
        self._finish(runner, "T2", "A06", "A10")
        self._finish(runner, "T3", "A05", "A10")
        runner.assert_all_done()

        replayed = MissionRunner.replay(
            "M1", ["T1", "T2", "T3"], runner.ledger.events(), task_nodes=nodes
        )
        replayed.assert_all_done()

    def test_self_review_is_rejected(self):
        runner = MissionRunner("M1", ["T1"])
        runner.release_ready_tasks()
        runner.transition("T1", TaskState.IN_PROGRESS, actor_id="A05")
        runner.transition("T1", TaskState.READY_FOR_VERIFICATION, actor_id="A05")
        runner.transition(
            "T1", TaskState.REVIEW, actor_id="A05", evidence_ids=("E1",)
        )
        with self.assertRaises(ValueError):
            runner.transition(
                "T1",
                TaskState.VERIFIED,
                actor_id="A05",
                evidence_ids=("E1",),
                reviewer_ids=("A05",),
            )

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
