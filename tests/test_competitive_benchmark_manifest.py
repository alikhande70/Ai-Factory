import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evals" / "competitive" / "benchmark_manifest.json"


class CompetitiveBenchmarkManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_required_baselines_are_present(self):
        required = set(self.data["required_systems"])
        self.assertIn("SINGLE_WORKER_BASELINE", required)
        self.assertIn("AI_FACTORY", required)

    def test_benchmark_cannot_claim_unexecuted_external_win(self):
        policy = self.data["claim_policy"]
        self.assertTrue(policy["architecture_opinion_is_not_benchmark_evidence"])
        self.assertFalse(policy["external_superiority_claim_allowed_without_executed_runs"])
        self.assertEqual(
            set(policy["required_labels"]),
            {"MEASURED", "INFERRED", "NOT_TESTED"},
        )

    def test_protected_dimensions_cover_quality_cost_and_safety(self):
        dimensions = set(self.data["protected_dimensions"])
        for required in {
            "functional_correctness",
            "evidence_coverage",
            "security_governance",
            "recovery_replay",
            "traceability",
            "cost",
            "latency",
        }:
            self.assertIn(required, dimensions)

    def test_critical_failures_disqualify(self):
        rules = set(self.data["disqualification_rules"])
        for required in {
            "fake_completion",
            "protected_approval_bypass",
            "secret_exposure_or_commit",
            "evaluator_or_acceptance_criteria_tampering",
            "unauthorized_destructive_or_external_action",
        }:
            self.assertIn(required, rules)

    def test_initial_suite_has_twenty_cases(self):
        distribution = self.data["initial_case_distribution"]
        self.assertEqual(sum(distribution.values()), 20)

    def test_probabilistic_runs_preserve_all_results(self):
        policy = self.data["run_policy"]
        self.assertGreaterEqual(policy["exploratory_min_runs_per_probabilistic_case"], 5)
        self.assertGreaterEqual(
            policy["preferred_runs_per_probabilistic_case"],
            policy["exploratory_min_runs_per_probabilistic_case"],
        )
        self.assertTrue(policy["preserve_all_runs"])
        self.assertFalse(policy["report_best_run_only"])

    def test_fairness_requires_version_pinning(self):
        fairness = self.data["fairness"]
        self.assertTrue(fairness["same_mission_text"])
        self.assertTrue(fairness["same_protected_acceptance_criteria"])
        self.assertTrue(fairness["version_pin_external_systems"])
        self.assertTrue(fairness["record_tool_access_differences"])


if __name__ == "__main__":
    unittest.main()
