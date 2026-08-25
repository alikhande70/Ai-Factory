from __future__ import annotations
from collections import defaultdict,deque
from dataclasses import dataclass
from enum import Enum
from .graph import TaskNode,can_run_in_parallel
class RetryDecision(str,Enum): RETRY="RETRY"; RECONCILE="RECONCILE"; STOP="STOP"
@dataclass(frozen=True)
class FailureContext: transient:bool; side_effecting:bool; outcome_known:bool; attempts:int; max_retries:int
def choose_execution_mode(task_count:int,independent_review_required:bool,specialist_domains:int)->str:
    return "single_worker" if task_count<=1 and not independent_review_required and specialist_domains<=1 else "pod"
def parallel_pairs(nodes:list[TaskNode])->list[tuple[str,str]]:
    return [(a.task_id,b.task_id) for i,a in enumerate(nodes) for b in nodes[i+1:] if can_run_in_parallel(a,b)]
def invalidate_downstream(changed_task_id:str,nodes:list[TaskNode])->set[str]:
    children=defaultdict(set)
    for node in nodes:
        for dep in node.dependencies:children[dep].add(node.task_id)
    stale=set(); queue=deque(children[changed_task_id])
    while queue:
        task_id=queue.popleft()
        if task_id in stale:continue
        stale.add(task_id);queue.extend(children[task_id])
    return stale
def retry_decision(ctx:FailureContext)->RetryDecision:
    if ctx.side_effecting and not ctx.outcome_known:return RetryDecision.RECONCILE
    if not ctx.transient or ctx.attempts>=ctx.max_retries:return RetryDecision.STOP
    return RetryDecision.RETRY
def protected_ambiguity_requires_human(*,protected:bool,ambiguity_material:bool)->bool:return protected and ambiguity_material
def budget_exhausted(*,used:int,limit:int)->bool:return used>=limit
def retrieved_content_can_grant_authority(_:str)->bool:return False
def completion_claim_supported(evidence_ids:tuple[str,...],checks_passed:bool)->bool:return bool(evidence_ids) and checks_passed
