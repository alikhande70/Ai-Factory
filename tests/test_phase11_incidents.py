from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from factory.runtime.catalog import SQLiteRuntimeCatalog
from factory.runtime.incidents import IncidentResponseStore


class Phase11IncidentResponseTests(unittest.TestCase):
    def _store(self, root: Path) -> tuple[SQLiteRuntimeCatalog, IncidentResponseStore]:
        catalog = SQLiteRuntimeCatalog(root / "runtime.db")
        store = IncidentResponseStore(root / "runtime.db", runtime_catalog=catalog)
        return catalog, store

    def _declare(self, store: IncidentResponseStore) -> None:
        store.declare(
            incident_id="INC-1",
            mission_id="MISSION-001",
            severity="SEV1",
            title="production integrity alert",
            declared_by="A11",
            affected_scope=("runtime-db", "api"),
        )

    def test_full_state_machine_requires_evidence_and_verified_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store = self._store(Path(tmp))
            self._declare(store)
            for state in ("TRIAGED", "CONTAINING", "CONTAINED", "RECOVERING", "MONITORING"):
                store.transition("INC-1", mission_id="MISSION-001", actor_id="A11", new_status=state)
            with self.assertRaisesRegex(RuntimeError, "incident_recovery_not_verified"):
                store.transition("INC-1", mission_id="MISSION-001", actor_id="A11", new_status="CLOSED")

            store.record_evidence(
                "INC-1",
                mission_id="MISSION-001",
                evidence_id="EV-RECOVERY",
                kind="verification",
                reference="test://recovery-pass",
                recorded_by="A10",
            )
            store.verify_recovery(
                "INC-1",
                mission_id="MISSION-001",
                actor_id="A10",
                evidence_id="EV-RECOVERY",
            )
            closed = store.transition("INC-1", mission_id="MISSION-001", actor_id="A11", new_status="CLOSED")
            self.assertTrue(closed.recovery_verified)
            self.assertEqual(closed.status, "CLOSED")
            store.verify_history("INC-1", mission_id="MISSION-001")

    def test_protected_action_cannot_execute_without_exact_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog, store = self._store(Path(tmp))
            self._declare(store)
            catalog.propose_action(
                proposal_id="AP-1",
                mission_id="MISSION-001",
                action_type="containment",
                target="production-api",
                protected=True,
            )
            store.plan_action(
                "INC-1",
                mission_id="MISSION-001",
                action_id="ACT-1",
                action_type="disable-endpoint",
                target="production-api",
                protected=True,
                proposal_id="AP-1",
                actor_id="A11",
            )
            with self.assertRaisesRegex(PermissionError, "human_approval_required"):
                store.mark_action_executed("INC-1", mission_id="MISSION-001", action_id="ACT-1", actor_id="A11")
            catalog.decide_action("AP-1", approved=True, decided_by="HUMAN", mission_id="MISSION-001")
            store.mark_action_executed("INC-1", mission_id="MISSION-001", action_id="ACT-1", actor_id="A11")
            store.verify_history("INC-1", mission_id="MISSION-001")

    def test_cross_mission_access_and_illegal_transition_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store = self._store(Path(tmp))
            self._declare(store)
            with self.assertRaisesRegex(PermissionError, "cross_mission_incident_access_denied"):
                store.get("INC-1", mission_id="MISSION-002")
            with self.assertRaisesRegex(RuntimeError, "illegal_incident_transition"):
                store.transition("INC-1", mission_id="MISSION-001", actor_id="A11", new_status="CONTAINED")

    def test_restart_preserves_state_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, store = self._store(root)
            self._declare(store)
            store.transition("INC-1", mission_id="MISSION-001", actor_id="A11", new_status="TRIAGED")

            reopened_catalog = SQLiteRuntimeCatalog(root / "runtime.db")
            reopened = IncidentResponseStore(root / "runtime.db", runtime_catalog=reopened_catalog)
            record = reopened.get("INC-1", mission_id="MISSION-001")
            self.assertEqual(record.status, "TRIAGED")
            reopened.verify_history("INC-1", mission_id="MISSION-001")

    def test_incident_event_tamper_is_detected(self) -> None:
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, store = self._store(root)
            self._declare(store)
            with sqlite3.connect(root / "runtime.db") as connection:
                connection.execute(
                    "UPDATE incident_events SET payload_json='{}' WHERE incident_id='INC-1' AND sequence=1"
                )
                connection.commit()
            with self.assertRaisesRegex(ValueError, "incident event mutation detected"):
                store.verify_history("INC-1", mission_id="MISSION-001")


if __name__ == "__main__":
    unittest.main()
