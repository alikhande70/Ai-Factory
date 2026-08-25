from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .graph import TaskNode, ready_tasks, validate_graph
from .ledger import AuditEvent, AuditLedger
from .state import TaskState, TransitionContext, validate_transition


@dataclass
class TaskRuntimeRecord:
    task_id: str
    state: TaskState = TaskState.BACKLOG
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    reviewer_ids: tuple[str, ...] = field(default_factory=tuple)
    worker_ids: tuple[str, ...] = field(default_factory=tuple)
    blocking_objections: tuple[str, ...] = field(default_factory=tuple)


class MissionRunner:
    """Deterministic Phase 1 mission runner.

    LLM workers propose work; this runtime owns canonical transition validation,
    dependency release, reviewer-independence enforcement and audit ordering.
    Canonical task state is committed only after the audit append succeeds.
    """

    def __init__(
        self,
        mission_id: str,
        task_ids: Iterable[str],
        ledger: AuditLedger | None = None,
        task_nodes: Iterable[TaskNode] | None = None,
    ) -> None:
        if not mission_id:
            raise ValueError("mission_id is required")
        ids = tuple(task_ids)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate task id")
        nodes = tuple(task_nodes or (TaskNode(task_id) for task_id in ids))
        validate_graph(list(nodes))
        if set(ids) != {node.task_id for node in nodes}:
            raise ValueError("task_ids and task_nodes must match")
        self.mission_id = mission_id
        self.tasks = {task_id: TaskRuntimeRecord(task_id) for task_id in ids}
        self.task_nodes = {node.task_id: node for node in nodes}
        self.ledger = ledger or AuditLedger()

    def transition(
        self,
        task_id: str,
        target: TaskState,
        *,
        actor_id: str,
        evidence_ids: tuple[str, ...] = (),
        reviewer_ids: tuple[str, ...] = (),
        blocking_objections: tuple[str, ...] = (),
        human_approval_id: str | None = None,
        event_id: str | None = None,
    ) -> AuditEvent:
        record = self._task(task_id)
        worker_ids = record.worker_ids
        if target is TaskState.IN_PROGRESS and actor_id not in worker_ids:
            worker_ids = tuple(sorted(set(worker_ids) | {actor_id}))
        ctx = TransitionContext(
            evidence_ids=evidence_ids,
            reviewer_ids=reviewer_ids,
            worker_ids=worker_ids,
            blocking_objections=blocking_objections,
            human_approval_id=human_approval_id,
        )
        validate_transition(record.state, target, ctx)

        previous = record.state
        event = self.ledger.append(
            event_id=event_id or f"EVT-{len(self.ledger.events()) + 1:06d}",
            mission_id=self.mission_id,
            actor_id=actor_id,
            event_type="TASK_STATE_TRANSITION",
            payload={
                "task_id": task_id,
                "from": previous.value,
                "to": target.value,
                "evidence_ids": list(evidence_ids),
                "reviewer_ids": list(reviewer_ids),
                "worker_ids": list(worker_ids),
                "blocking_objections": list(blocking_objections),
                "human_approval_id": human_approval_id,
            },
        )

        record.state = target
        record.worker_ids = worker_ids
        if evidence_ids:
            record.evidence_ids = evidence_ids
        if reviewer_ids:
            record.reviewer_ids = reviewer_ids
        record.blocking_objections = blocking_objections
        return event

    def release_ready_tasks(self, *, actor_id: str = "CONTROL-PLANE") -> tuple[str, ...]:
        """Move dependency-satisfied BACKLOG tasks to READY and audit each release."""
        states = {task_id: record.state.value for task_id, record in self.tasks.items()}
        task_ids = ready_tasks(tuple(self.task_nodes.values()), states)
        for task_id in task_ids:
            self.transition(task_id, TaskState.READY, actor_id=actor_id)
        return task_ids

    def _task(self, task_id: str) -> TaskRuntimeRecord:
        try:
            return self.tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"unknown task: {task_id}") from exc

    def assert_all_done(self) -> None:
        unfinished = sorted(task_id for task_id, record in self.tasks.items() if record.state is not TaskState.DONE)
        if unfinished:
            raise ValueError(f"unfinished tasks: {unfinished}")
        self.ledger.verify_integrity()

    @classmethod
    def replay(
        cls,
        mission_id: str,
        task_ids: Iterable[str],
        events: Iterable[AuditEvent],
        task_nodes: Iterable[TaskNode] | None = None,
    ) -> "MissionRunner":
        source_ledger = AuditLedger.from_events(events)
        runner = cls(mission_id, task_ids, AuditLedger(), task_nodes=task_nodes)
        for event in source_ledger.events(mission_id):
            if event.event_type != "TASK_STATE_TRANSITION":
                continue
            payload = event.payload
            runner.transition(
                payload["task_id"],
                TaskState(payload["to"]),
                actor_id=event.actor_id,
                evidence_ids=tuple(payload.get("evidence_ids", ())),
                reviewer_ids=tuple(payload.get("reviewer_ids", ())),
                blocking_objections=tuple(payload.get("blocking_objections", ())),
                human_approval_id=payload.get("human_approval_id"),
                event_id=event.event_id,
            )
        return runner
