from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import unittest

from factory.reliability.readiness import (
    MANDATORY_CODE_CONTROLS,
    MANDATORY_PRODUCTION_CONTROLS,
    ReadinessControl,
    evaluate_release_readiness,
)


class Phase11ReadinessTests(unittest.TestCase):
    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _passing_code_controls(self) -> list[ReadinessControl]:
        return [
            ReadinessControl(control_id=control_id, status="PASS", evidence_ref=f"test://{control_id}")
            for control_id in MANDATORY_CODE_CONTROLS
        ]

    def test_code_qualified_is_not_production_ready_when_external_controls_unverified(self) -> None:
        controls = self._passing_code_controls() + [
            ReadinessControl("github_branch_protection", "FAIL"),
            ReadinessControl("production_secret_provider", "UNVERIFIED"),
            ReadinessControl("offsite_recovery", "UNVERIFIED"),
            ReadinessControl("production_slo_evidence", "UNVERIFIED"),
        ]
        report = evaluate_release_readiness(controls)
        self.assertEqual(report.stage, "CODE_QUALIFIED")
        self.assertTrue(report.code_qualified)
        self.assertFalse(report.production_ready)
        self.assertEqual({b.control_id for b in report.blockers if b.scope == "PRODUCTION"}, set(MANDATORY_PRODUCTION_CONTROLS))
        with self.assertRaisesRegex(RuntimeError, "production_readiness_not_proven"):
            report.assert_production_ready()

    def test_missing_required_control_is_unverified_not_silently_ignored(self) -> None:
        controls = self._passing_code_controls()
        controls = [c for c in controls if c.control_id != "incident_response_state_machine"]
        report = evaluate_release_readiness(controls)
        self.assertEqual(report.stage, "NOT_QUALIFIED")
        blocker = next(b for b in report.blockers if b.control_id == "incident_response_state_machine")
        self.assertEqual(blocker.status, "UNVERIFIED")
        self.assertEqual(blocker.scope, "CODE")

    def test_failed_code_control_blocks_even_if_production_controls_pass(self) -> None:
        controls = self._passing_code_controls()
        controls = [
            ReadinessControl(c.control_id, "FAIL" if c.control_id == "backup_restore_integrity" else c.status, c.evidence_ref if c.control_id != "backup_restore_integrity" else None)
            for c in controls
        ]
        controls.extend(
            ReadinessControl(control_id, "PASS", f"prod://{control_id}")
            for control_id in MANDATORY_PRODUCTION_CONTROLS
        )
        report = evaluate_release_readiness(controls)
        self.assertEqual(report.stage, "NOT_QUALIFIED")
        self.assertFalse(report.code_qualified)
        self.assertFalse(report.production_ready)

    def test_all_required_controls_with_evidence_can_reach_production_ready(self) -> None:
        controls = self._passing_code_controls() + [
            ReadinessControl(control_id, "PASS", f"prod://{control_id}")
            for control_id in MANDATORY_PRODUCTION_CONTROLS
        ]
        report = evaluate_release_readiness(controls)
        self.assertEqual(report.stage, "PRODUCTION_READY")
        self.assertTrue(report.production_ready)
        self.assertEqual(report.blockers, ())
        report.assert_production_ready()

    def test_pass_control_requires_evidence_and_duplicates_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "PASS readiness control requires evidence_ref"):
            ReadinessControl("control", "PASS")
        duplicate = ReadinessControl("x", "UNVERIFIED")
        with self.assertRaisesRegex(ValueError, "duplicate readiness control"):
            evaluate_release_readiness((duplicate, duplicate), required_code_controls=(), required_production_controls=())

    def test_schema_matches_report_shape(self) -> None:
        schema = json.loads((self.repo_root / "schemas" / "release-readiness.schema.json").read_text(encoding="utf-8"))
        report = evaluate_release_readiness(self._passing_code_controls())
        payload = asdict(report)
        self.assertEqual(set(payload), set(schema["required"]))
        self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
