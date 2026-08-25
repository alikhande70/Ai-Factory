import tempfile
import unittest
from pathlib import Path

from factory.runtime.adapters import WorkspaceIsolation
from factory.runtime.catalog import SQLiteRuntimeCatalog
from factory.runtime.intake import MissionIntakeService
from factory.runtime.policy import PolicyEngineV0
from factory.runtime.tracing import REDACTED, SQLiteTracer


class Phase2ServiceTests(unittest.TestCase):
    def test_mission_intake_normalizes_and_rejects_bad_quality(self):
        service = MissionIntakeService()
        mission = service.prepare(
            mission_id=" M-1 ",
            objective=" Build a verified service ",
            quality_profile="production",
            constraints=(" durable ", ""),
        )
        self.assertEqual(mission.mission_id, "M-1")
        self.assertEqual(mission.quality_profile, "PRODUCTION")
        self.assertEqual(mission.constraints, ("durable",))
        with self.assertRaises(ValueError):
            service.prepare(mission_id="M-2", objective="x", quality_profile="FAST")

    def test_agent_registry_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.db"
            first = SQLiteRuntimeCatalog(path)
            first.register_agent("A06", "Backend", ("code.write", "tests.run"))
            restored = SQLiteRuntimeCatalog(path).get_agent("A06")
            self.assertEqual(restored["role"], "Backend")
            self.assertEqual(restored["capabilities"], ("code.write", "tests.run"))
            self.assertTrue(restored["active"])

    def test_artifact_versions_are_immutable_and_latest_is_restorable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.db"
            catalog = SQLiteRuntimeCatalog(path)
            one = catalog.add_artifact(
                mission_id="M1", artifact_id="PRD", content="v1", created_by="A02"
            )
            two = catalog.add_artifact(
                mission_id="M1", artifact_id="PRD", content="v2", created_by="A02"
            )
            self.assertEqual(one["version"], 1)
            self.assertEqual(two["version"], 2)
            latest = SQLiteRuntimeCatalog(path).latest_artifact("M1", "PRD")
            self.assertEqual(latest["version"], 2)
            self.assertEqual(latest["content_text"], "v2")
            self.assertNotEqual(one["content_hash"], two["content_hash"])

    def test_budget_exhaustion_does_not_mutate_consumed_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.db"
            catalog = SQLiteRuntimeCatalog(path)
            catalog.set_budget("M1", 10)
            self.assertEqual(catalog.consume_budget("M1", 7), (7, 10))
            with self.assertRaisesRegex(RuntimeError, "budget_exhausted"):
                catalog.consume_budget("M1", 4)
            self.assertEqual(catalog.consume_budget("M1", 3), (10, 10))

    def test_approval_is_single_decision_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.db"
            catalog = SQLiteRuntimeCatalog(path)
            catalog.propose_action(
                proposal_id="P1",
                mission_id="M1",
                action_type="deploy",
                target="production",
                protected=True,
            )
            self.assertEqual(catalog.approval_status("P1"), "PENDING")
            catalog.decide_action("P1", approved=True, decided_by="HUMAN")
            self.assertEqual(SQLiteRuntimeCatalog(path).approval_status("P1"), "APPROVED")
            with self.assertRaisesRegex(RuntimeError, "approval_already_decided"):
                catalog.decide_action("P1", approved=False, decided_by="A01")

    def test_policy_requires_capability_budget_and_protected_approval(self):
        policy = PolicyEngineV0()
        denied = policy.authorize(
            capability_required="deploy.write",
            agent_capabilities=("code.write",),
            protected=True,
            approval_status="APPROVED",
            budget_available=True,
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "missing_capability")
        denied = policy.authorize(
            capability_required="deploy.write",
            agent_capabilities=("deploy.write",),
            protected=True,
            approval_status="PENDING",
            budget_available=True,
        )
        self.assertEqual(denied.reason, "human_approval_required")
        allowed = policy.authorize(
            capability_required="deploy.write",
            agent_capabilities=("deploy.write",),
            protected=True,
            approval_status="APPROVED",
            budget_available=True,
        )
        self.assertTrue(allowed.allowed)

    def test_trace_redaction_is_recursive_and_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.db"
            tracer = SQLiteTracer(path)
            tracer.trace(
                mission_id="M1",
                actor_id="A08",
                event_name="provider.call",
                payload={"safe": "ok", "nested": {"access_value": "should-not-persist"}},
            )
            event = SQLiteTracer(path).events("M1")[0]
            self.assertEqual(event["payload"]["safe"], "ok")
            self.assertEqual(event["payload"]["nested"]["access_value"], REDACTED)
            self.assertNotIn("should-not-persist", str(event))

    def test_workspace_leases_are_deterministic_and_scope_normalized(self):
        isolation = WorkspaceIsolation()
        first = isolation.lease(
            mission_id="M1", task_id="T1", write_scopes=(" api/ ", "api/", "tests/")
        )
        second = isolation.lease(
            mission_id="M1", task_id="T1", write_scopes=("tests/", "api/")
        )
        self.assertEqual(first.workspace_id, second.workspace_id)
        self.assertEqual(first.write_scopes, ("api/", "tests/"))


if __name__ == "__main__":
    unittest.main()
