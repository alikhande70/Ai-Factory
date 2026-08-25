import unittest

from factory.control_plane.ledger import AuditEvent, AuditLedger
from factory.control_plane.runner import MissionRunner
from factory.control_plane.state import TaskState


class AuditLedgerTests(unittest.TestCase):
    def test_hash_chain_and_duplicate_ids(self):
        ledger = AuditLedger()
        first = ledger.append(
            event_id="EVT-1",
            mission_id="M-1",
            actor_id="SYSTEM",
            event_type="TEST",
            payload={"value": 1},
            created_at="2026-08-25T00:00:00+00:00",
        )
        second = ledger.append(
            event_id="EVT-2",
            mission_id="M-1",
            actor_id="SYSTEM",
            event_type="TEST",
            payload={"value": 2},
            created_at="2026-08-25T00:00:01+00:00",
        )
        self.assertEqual(second.previous_hash, first.event_hash)
        ledger.verify_integrity()
        with self.assertRaises(ValueError):
            ledger.append(
                event_id="EVT-2",
                mission_id="M-1",
                actor_id="SYSTEM",
                event_type="TEST",
                payload={},
            )

    def test_tampering_is_detected(self):
        ledger = AuditLedger()
        event = ledger.append(
            event_id="EVT-1",
            mission_id="M-1",
            actor_id="SYSTEM",
            event_type="TEST",
            payload={"safe": True},
            created_at="2026-08-25T00:00:00+00:00",
        )
        forged = AuditEvent(
            sequence=event.sequence,
            event_id=event.event_id,
            mission_id=event.mission_id,
            actor_id=event.actor_id,
            event_type=event.event_type,
            payload={"safe": False},
            created_at=event.created_at,
            previous_hash=event.previous_hash,
            event_hash=event.event_hash,
        )
        with self.assertRaises(ValueError):
            AuditLedger.from_events([forged])


class MissionRunnerTests(unittest.TestCase):
    def _complete_task(self, runner: MissionRunner, task_id: str) -> None:
        runner.transition(task_id, TaskState.READY, actor_id="A01")
        runner.transition(task_id, TaskState.IN_PROGRESS, actor_id="A05")
        runner.transition(task_id, TaskState.READY_FOR_VERIFICATION, actor_id="A05")
        runner.transition(
            task_id,
            TaskState.REVIEW,
            actor_id="A10",
            evidence_ids=("EVID-1",),
        )
        runner.transition(
            task_id,
            TaskState.VERIFIED,
            actor_id="A10",
            evidence_ids=("EVID-1",),
            reviewer_ids=("A10",),
        )
        runner.transition(task_id, TaskState.DONE, actor_id="CONTROL-PLANE")

    def test_create_verify_review_done_is_audited(self):
        runner = MissionRunner("M-1", ["T-1"])
        self._complete_task(runner, "T-1")
        runner.assert_all_done()
        events = runner.ledger.events("M-1")
        self.assertEqual(len(events), 6)
        self.assertEqual(events[-1].payload["to"], "DONE")

    def test_replay_reconstructs_canonical_state(self):
        runner = MissionRunner("M-1", ["T-1"])
        self._complete_task(runner, "T-1")
        replayed = MissionRunner.replay("M-1", ["T-1"], runner.ledger.events())
        self.assertEqual(replayed.tasks["T-1"].state, TaskState.DONE)
        replayed.assert_all_done()

    def test_invalid_transition_creates_no_event(self):
        runner = MissionRunner("M-1", ["T-1"])
        with self.assertRaises(ValueError):
            runner.transition("T-1", TaskState.DONE, actor_id="A01")
        self.assertEqual(runner.ledger.events(), ())

    def test_ledger_failure_does_not_mutate_canonical_state(self):
        runner = MissionRunner("M-1", ["T-1"])
        runner.transition("T-1", TaskState.READY, actor_id="A01", event_id="EVT-1")
        self.assertEqual(runner.tasks["T-1"].state, TaskState.READY)
        with self.assertRaises(ValueError):
            runner.transition("T-1", TaskState.IN_PROGRESS, actor_id="A05", event_id="EVT-1")
        self.assertEqual(runner.tasks["T-1"].state, TaskState.READY)
        self.assertEqual(len(runner.ledger.events()), 1)

    def test_blocking_objection_prevents_verified_and_is_not_logged_as_success(self):
        runner = MissionRunner("M-1", ["T-1"])
        runner.transition("T-1", TaskState.READY, actor_id="A01")
        runner.transition("T-1", TaskState.IN_PROGRESS, actor_id="A05")
        runner.transition("T-1", TaskState.READY_FOR_VERIFICATION, actor_id="A05")
        runner.transition("T-1", TaskState.REVIEW, actor_id="A09", evidence_ids=("E1",))
        before = len(runner.ledger.events())
        with self.assertRaises(ValueError):
            runner.transition(
                "T-1",
                TaskState.VERIFIED,
                actor_id="A09",
                evidence_ids=("E1",),
                reviewer_ids=("A09",),
                blocking_objections=("OBJ-1",),
            )
        self.assertEqual(len(runner.ledger.events()), before)
        self.assertEqual(runner.tasks["T-1"].state, TaskState.REVIEW)


if __name__ == "__main__":
    unittest.main()
