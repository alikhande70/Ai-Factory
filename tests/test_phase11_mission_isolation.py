from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from factory.runtime.catalog import SQLiteRuntimeCatalog
from factory.runtime.mission_scope import MissionScopedCatalog


class Phase11MissionIsolationTests(unittest.TestCase):
    def test_shared_catalog_keeps_artifact_budget_and_approval_state_mission_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = SQLiteRuntimeCatalog(Path(directory) / "runtime.db")
            alpha = MissionScopedCatalog(catalog, "MISSION-ALPHA")
            beta = MissionScopedCatalog(catalog, "MISSION-BETA")

            alpha.add_artifact(artifact_id="SPEC", content="alpha", created_by="A02")
            beta.add_artifact(artifact_id="SPEC", content="beta", created_by="A02")
            self.assertEqual(alpha.latest_artifact("SPEC")["content_text"], "alpha")
            self.assertEqual(beta.latest_artifact("SPEC")["content_text"], "beta")

            alpha.set_budget(10)
            beta.set_budget(20)
            self.assertEqual(alpha.consume_budget(3), (3, 10))
            self.assertEqual(beta.consume_budget(5), (5, 20))

            alpha.propose_action(
                proposal_id="APPROVAL-ALPHA",
                action_type="PRODUCTION_DEPLOY",
                target="service-alpha",
                protected=True,
            )
            beta.propose_action(
                proposal_id="APPROVAL-BETA",
                action_type="PRODUCTION_DEPLOY",
                target="service-beta",
                protected=True,
            )

            self.assertEqual(alpha.approval_status("APPROVAL-ALPHA"), "PENDING")
            self.assertEqual(beta.approval_status("APPROVAL-BETA"), "PENDING")
            with self.assertRaisesRegex(PermissionError, "cross_mission_access_denied"):
                alpha.approval_status("APPROVAL-BETA")
            with self.assertRaisesRegex(PermissionError, "cross_mission_access_denied"):
                beta.decide_action(
                    "APPROVAL-ALPHA",
                    approved=True,
                    decided_by="HUMAN-OWNER",
                )

            self.assertEqual(
                alpha.decide_action(
                    "APPROVAL-ALPHA",
                    approved=True,
                    decided_by="HUMAN-OWNER",
                ),
                "APPROVED",
            )
            self.assertEqual(beta.approval_status("APPROVAL-BETA"), "PENDING")

    def test_empty_mission_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = SQLiteRuntimeCatalog(Path(directory) / "runtime.db")
            with self.assertRaises(ValueError):
                MissionScopedCatalog(catalog, "")


if __name__ == "__main__":
    unittest.main()
