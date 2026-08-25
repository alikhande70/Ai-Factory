from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class AgentRecord: agent_id:str; role:str; capabilities:frozenset[str]; write_scopes:tuple[str,...]; enabled:bool=True
class AgentRegistry:
    def __init__(self,agents:list[AgentRecord]|None=None)->None:self._agents={a.agent_id:a for a in (agents or [])}
    def register(self,agent:AgentRecord)->None:
        if agent.agent_id in self._agents:raise ValueError(f"duplicate agent: {agent.agent_id}")
        self._agents[agent.agent_id]=agent
    def get(self,agent_id:str)->AgentRecord:
        try:return self._agents[agent_id]
        except KeyError as exc:raise KeyError(f"unknown agent: {agent_id}") from exc
    def candidates(self,capability:str)->list[AgentRecord]:return sorted([a for a in self._agents.values() if a.enabled and capability in a.capabilities],key=lambda a:a.agent_id)
