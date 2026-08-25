from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class TaskNode:
    task_id:str; dependencies:tuple[str,...]=(); write_scopes:tuple[str,...]=()

def validate_graph(nodes:list[TaskNode])->None:
    by_id={n.task_id:n for n in nodes}
    if len(by_id)!=len(nodes): raise ValueError("duplicate task id")
    for node in nodes:
        missing=[d for d in node.dependencies if d not in by_id]
        if missing: raise ValueError(f"missing dependencies for {node.task_id}: {missing}")
        if node.task_id in node.dependencies: raise ValueError(f"self dependency: {node.task_id}")
    visiting:set[str]=set(); visited:set[str]=set()
    def visit(task_id:str)->None:
        if task_id in visited:return
        if task_id in visiting:raise ValueError("dependency cycle detected")
        visiting.add(task_id)
        for dep in by_id[task_id].dependencies:visit(dep)
        visiting.remove(task_id);visited.add(task_id)
    for task_id in by_id:visit(task_id)

def can_run_in_parallel(a:TaskNode,b:TaskNode)->bool:
    if a.task_id in b.dependencies or b.task_id in a.dependencies:return False
    return set(a.write_scopes).isdisjoint(set(b.write_scopes))

def ready_tasks(nodes:tuple[TaskNode,...], states:dict[str,str])->tuple[str,...]:
    """Return BACKLOG tasks whose dependencies are all DONE.

    The control plane, not an LLM worker, decides dependency readiness.
    """
    validate_graph(list(nodes))
    by_id={node.task_id:node for node in nodes}
    if set(by_id) != set(states):
        raise ValueError("states must exactly match graph task ids")
    ready=[]
    for task_id,node in by_id.items():
        if states[task_id] != "BACKLOG":
            continue
        if all(states[dep] == "DONE" for dep in node.dependencies):
            ready.append(task_id)
    return tuple(sorted(ready))
