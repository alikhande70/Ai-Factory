from __future__ import annotations
from dataclasses import dataclass
PROTECTED_CAPABILITIES=frozenset({"production.deploy","billing.modify","finance.transact","secrets.rotate","identity.act_as_owner","legal.accept","data.production_destructive"})
@dataclass(frozen=True)
class CapabilityGrant: agent_id:str; capabilities:frozenset[str]
@dataclass(frozen=True)
class Budget:
    max_tokens:int; max_tool_calls:int; max_retries:int; max_parallel_tasks:int
    def validate(self)->None:
        if min(self.max_tokens,self.max_tool_calls,self.max_retries,self.max_parallel_tasks)<0: raise ValueError("budget values must be non-negative")
def authorize(grant:CapabilityGrant,capability:str,human_approval:bool=False)->bool:
    if capability not in grant.capabilities:return False
    if capability in PROTECTED_CAPABILITIES and not human_approval:return False
    return True
