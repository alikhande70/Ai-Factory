from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

class TaskState(str, Enum):
    BACKLOG="BACKLOG"; READY="READY"; IN_PROGRESS="IN_PROGRESS"; BLOCKED="BLOCKED"; READY_FOR_VERIFICATION="READY_FOR_VERIFICATION"; REVIEW="REVIEW"; CHANGES_REQUESTED="CHANGES_REQUESTED"; VERIFIED="VERIFIED"; DONE="DONE"; FAILED="FAILED"; CANCELLED="CANCELLED"; STALE="STALE"; AWAITING_HUMAN_APPROVAL="AWAITING_HUMAN_APPROVAL"

_ALLOWED={
 TaskState.BACKLOG:frozenset({TaskState.READY,TaskState.CANCELLED}),
 TaskState.READY:frozenset({TaskState.IN_PROGRESS,TaskState.BLOCKED,TaskState.CANCELLED,TaskState.STALE}),
 TaskState.IN_PROGRESS:frozenset({TaskState.BLOCKED,TaskState.READY_FOR_VERIFICATION,TaskState.FAILED,TaskState.CANCELLED,TaskState.AWAITING_HUMAN_APPROVAL,TaskState.STALE}),
 TaskState.BLOCKED:frozenset({TaskState.READY,TaskState.IN_PROGRESS,TaskState.CANCELLED,TaskState.FAILED,TaskState.STALE}),
 TaskState.READY_FOR_VERIFICATION:frozenset({TaskState.REVIEW,TaskState.CHANGES_REQUESTED,TaskState.FAILED,TaskState.STALE}),
 TaskState.REVIEW:frozenset({TaskState.VERIFIED,TaskState.CHANGES_REQUESTED,TaskState.FAILED,TaskState.STALE}),
 TaskState.CHANGES_REQUESTED:frozenset({TaskState.IN_PROGRESS,TaskState.CANCELLED,TaskState.STALE}),
 TaskState.VERIFIED:frozenset({TaskState.DONE,TaskState.STALE}), TaskState.DONE:frozenset({TaskState.STALE}),
 TaskState.FAILED:frozenset({TaskState.READY,TaskState.CANCELLED}), TaskState.CANCELLED:frozenset(),
 TaskState.STALE:frozenset({TaskState.READY,TaskState.CANCELLED}),
 TaskState.AWAITING_HUMAN_APPROVAL:frozenset({TaskState.IN_PROGRESS,TaskState.CANCELLED,TaskState.FAILED,TaskState.STALE})}

@dataclass(frozen=True)
class TransitionContext:
    evidence_ids: tuple[str,...]=field(default_factory=tuple); reviewer_ids: tuple[str,...]=field(default_factory=tuple); blocking_objections: tuple[str,...]=field(default_factory=tuple); human_approval_id: str|None=None

def validate_transition(current:TaskState,target:TaskState,ctx:TransitionContext|None=None)->None:
    ctx=ctx or TransitionContext()
    if target not in _ALLOWED[current]: raise ValueError(f"illegal transition: {current.value} -> {target.value}")
    if target is TaskState.REVIEW and not ctx.evidence_ids: raise ValueError("REVIEW requires evidence")
    if target is TaskState.VERIFIED:
        if not ctx.evidence_ids: raise ValueError("VERIFIED requires evidence")
        if not ctx.reviewer_ids: raise ValueError("VERIFIED requires an independent reviewer")
        if ctx.blocking_objections: raise ValueError("VERIFIED forbidden while blocking objections exist")
    if current is TaskState.AWAITING_HUMAN_APPROVAL and target is TaskState.IN_PROGRESS and not ctx.human_approval_id: raise ValueError("resuming protected work requires human approval evidence")

def allowed_targets(current:TaskState)->Iterable[TaskState]: return tuple(sorted(_ALLOWED[current],key=lambda s:s.value))
