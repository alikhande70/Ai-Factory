import unittest

from factory.interoperability import (
    ExternalCapability,
    ExternalProvenance,
    ExternalResult,
    InteropPolicyGuard,
    InteropReliabilityBridge,
)
from factory.reliability import OperationSpec


class Phase7PolicyReliabilityTests(unittest.TestCase):
    def capability(self, *, effect_class="EXTERNAL_WRITE"):
        return ExternalCapability(
            capability_id="mcp:endpoint:deploy",
            name="deploy",
            effect_class=effect_class,
            required_factory_capability="deploy:preview",
            provenance=ExternalProvenance(
                protocol="MCP",
                protocol_version="2026-07-28",
                endpoint_id="endpoint",
            ),
        )

    def result(self, status):
        return ExternalResult(
            request_id="REQ-1",
            correlation_id="CORR-1",
            status=status,
            payload={},
            provenance=ExternalProvenance(
                protocol="MCP",
                protocol_version="2026-07-28",
                endpoint_id="endpoint",
            ),
        )

    def external_operation(self):
        return OperationSpec(
            operation_id="OP-1",
            mission_id="MISSION-1",
            effect_class="EXTERNAL_WRITE",
            max_attempts=3,
            timeout_seconds=10,
            idempotency_key="MISSION-1:OP-1",
            reconciliation_supported=True,
        )

    def test_policy_guard_requires_capability_budget_and_human_approval_when_protected(self):
        guard = InteropPolicyGuard()
        capability = self.capability()

        missing = guard.authorize(
            capability=capability,
            factory_capabilities=("repo:read",),
            protected=True,
            approval_status="APPROVED",
            budget_available=True,
        )
        self.assertFalse(missing.allowed)
        self.assertEqual(missing.reason, "missing_capability")

        budget = guard.authorize(
            capability=capability,
            factory_capabilities=("deploy:preview",),
            protected=True,
            approval_status="APPROVED",
            budget_available=False,
        )
        self.assertFalse(budget.allowed)
        self.assertEqual(budget.reason, "budget_exhausted")

        approval = guard.authorize(
            capability=capability,
            factory_capabilities=("deploy:preview",),
            protected=True,
            approval_status=None,
            budget_available=True,
        )
        self.assertFalse(approval.allowed)
        self.assertEqual(approval.reason, "human_approval_required")

        allowed = guard.authorize(
            capability=capability,
            factory_capabilities=("deploy:preview",),
            protected=True,
            approval_status="APPROVED",
            budget_available=True,
        )
        self.assertTrue(allowed.allowed)

    def test_unknown_external_write_maps_to_reconcile_not_retry(self):
        bridge = InteropReliabilityBridge()
        decision = bridge.decide(
            operation=self.external_operation(),
            capability=self.capability(),
            result=self.result("UNKNOWN"),
            attempt_number=1,
        )
        self.assertEqual(decision.action, "RECONCILE")
        self.assertEqual(decision.reason, "external_write_outcome_unknown")

    def test_failed_external_result_is_terminal_unless_explicitly_retryable(self):
        bridge = InteropReliabilityBridge()
        terminal = bridge.decide(
            operation=self.external_operation(),
            capability=self.capability(),
            result=self.result("FAILED"),
            attempt_number=1,
        )
        self.assertEqual(terminal.action, "STOP")
        retry = bridge.decide(
            operation=self.external_operation(),
            capability=self.capability(),
            result=self.result("FAILED"),
            attempt_number=1,
            retryable_failure=True,
        )
        self.assertEqual(retry.action, "RETRY")

    def test_input_required_is_not_treated_as_execution_failure_or_approval(self):
        bridge = InteropReliabilityBridge()
        with self.assertRaisesRegex(RuntimeError, "input-required"):
            bridge.decide(
                operation=self.external_operation(),
                capability=self.capability(),
                result=self.result("INPUT_REQUIRED"),
                attempt_number=1,
            )

    def test_effect_class_mismatch_is_rejected_before_reliability_decision(self):
        bridge = InteropReliabilityBridge()
        with self.assertRaisesRegex(ValueError, "effect_class"):
            bridge.decide(
                operation=self.external_operation(),
                capability=self.capability(effect_class="READ_ONLY"),
                result=self.result("SUCCEEDED"),
                attempt_number=1,
            )


if __name__ == "__main__":
    unittest.main()
