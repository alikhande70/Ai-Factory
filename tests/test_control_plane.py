import unittest
from factory.control_plane.graph import TaskNode,can_run_in_parallel,validate_graph
from factory.control_plane.policy import Budget,CapabilityGrant,authorize
from factory.control_plane.registry import AgentRecord,AgentRegistry
from factory.control_plane.state import TaskState,TransitionContext,validate_transition
class StateTests(unittest.TestCase):
 def test_happy_path(self):
  validate_transition(TaskState.BACKLOG,TaskState.READY);validate_transition(TaskState.READY,TaskState.IN_PROGRESS);validate_transition(TaskState.IN_PROGRESS,TaskState.READY_FOR_VERIFICATION);validate_transition(TaskState.READY_FOR_VERIFICATION,TaskState.REVIEW,TransitionContext(evidence_ids=("E1",)));validate_transition(TaskState.REVIEW,TaskState.VERIFIED,TransitionContext(evidence_ids=("E1",),reviewer_ids=("A10",)));validate_transition(TaskState.VERIFIED,TaskState.DONE)
 def test_done_cannot_skip_verification(self):
  with self.assertRaises(ValueError):validate_transition(TaskState.IN_PROGRESS,TaskState.DONE)
 def test_blocking_objection_prevents_verified(self):
  with self.assertRaises(ValueError):validate_transition(TaskState.REVIEW,TaskState.VERIFIED,TransitionContext(evidence_ids=("E1",),reviewer_ids=("A09",),blocking_objections=("OBJ-1",)))
 def test_human_gate_requires_approval_record(self):
  with self.assertRaises(ValueError):validate_transition(TaskState.AWAITING_HUMAN_APPROVAL,TaskState.IN_PROGRESS)
  validate_transition(TaskState.AWAITING_HUMAN_APPROVAL,TaskState.IN_PROGRESS,TransitionContext(human_approval_id="APR-1"))
class GraphTests(unittest.TestCase):
 def test_cycle_is_rejected(self):
  with self.assertRaises(ValueError):validate_graph([TaskNode("A",("B",)),TaskNode("B",("A",))])
 def test_parallel_when_write_scopes_disjoint(self):self.assertTrue(can_run_in_parallel(TaskNode("A",write_scopes=("frontend/",)),TaskNode("B",write_scopes=("backend/",))))
 def test_overlapping_write_scope_serialized(self):self.assertFalse(can_run_in_parallel(TaskNode("A",write_scopes=("backend/",)),TaskNode("B",write_scopes=("backend/",))))
class PolicyTests(unittest.TestCase):
 def test_natural_language_does_not_grant_capability(self):self.assertFalse(authorize(CapabilityGrant("A05",frozenset({"repo.read"})),"production.deploy",True))
 def test_protected_capability_requires_human_gate(self):
  g=CapabilityGrant("A11",frozenset({"production.deploy"}));self.assertFalse(authorize(g,"production.deploy"));self.assertTrue(authorize(g,"production.deploy",True))
 def test_budget_rejects_negative_values(self):
  with self.assertRaises(ValueError):Budget(100,10,-1,2).validate()
class RegistryTests(unittest.TestCase):
 def test_registry_routes_by_capability(self):
  r=AgentRegistry([AgentRecord("A05","Frontend",frozenset({"frontend.write"}),("frontend/",)),AgentRecord("A06","Backend",frozenset({"backend.write"}),("backend/",))]);self.assertEqual([a.agent_id for a in r.candidates("backend.write")],["A06"])
if __name__=="__main__":unittest.main()
