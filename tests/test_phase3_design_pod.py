import unittest

from factory.design_pod import (
    AcceptanceCriterion,
    ArchitectureDecision,
    DesignBundle,
    DesignBundleValidator,
    ProductRequirement,
    UXFlow,
)


class DesignPodTests(unittest.TestCase):
    def make_valid_bundle(self) -> DesignBundle:
        return DesignBundle(
            mission_id="MISSION-DESIGN-1",
            product_summary="A simple booking app",
            non_goals=("Payments",),
            requirements=(
                ProductRequirement("REQ-1", "User can create a booking", "MUST"),
                ProductRequirement("REQ-2", "User can view bookings", "SHOULD"),
            ),
            acceptance_criteria=(
                AcceptanceCriterion("AC-1", "REQ-1", "Given a valid slot, booking is created", "integration test"),
            ),
            architecture_decisions=(
                ArchitectureDecision("ADR-1", "Single service", "Use one application service", "Simplest reliable boundary", ("REQ-1",)),
            ),
            ux_flows=(
                UXFlow("UX-1", "Create booking", "user", ("Choose slot", "Confirm booking", "See confirmation"), ("REQ-1",)),
            ),
            assumptions=("Authenticated user",),
            risks=("Concurrent slot selection",),
        )

    def test_valid_bundle_is_build_ready(self):
        validator = DesignBundleValidator()
        self.assertTrue(validator.is_build_ready(self.make_valid_bundle()))
        self.assertEqual(validator.validate(self.make_valid_bundle()), ())

    def test_must_requirement_without_acceptance_is_blocked(self):
        bundle = self.make_valid_bundle()
        bundle = DesignBundle(
            mission_id=bundle.mission_id,
            product_summary=bundle.product_summary,
            non_goals=bundle.non_goals,
            requirements=bundle.requirements,
            acceptance_criteria=(),
            architecture_decisions=bundle.architecture_decisions,
            ux_flows=bundle.ux_flows,
            assumptions=bundle.assumptions,
            risks=bundle.risks,
        )
        codes = {finding.code for finding in DesignBundleValidator().validate(bundle)}
        self.assertIn("MUST_WITHOUT_ACCEPTANCE_CRITERION", codes)
        self.assertFalse(DesignBundleValidator().is_build_ready(bundle))

    def test_orphan_cross_role_references_are_blocked(self):
        bundle = self.make_valid_bundle()
        bundle = DesignBundle(
            mission_id=bundle.mission_id,
            product_summary=bundle.product_summary,
            non_goals=bundle.non_goals,
            requirements=bundle.requirements,
            acceptance_criteria=bundle.acceptance_criteria + (
                AcceptanceCriterion("AC-X", "REQ-X", "Unknown", "test"),
            ),
            architecture_decisions=bundle.architecture_decisions + (
                ArchitectureDecision("ADR-X", "Bad ref", "none", "test", ("REQ-X",)),
            ),
            ux_flows=bundle.ux_flows + (
                UXFlow("UX-X", "Bad flow", "user", ("step",), ("REQ-X",)),
            ),
            assumptions=bundle.assumptions,
            risks=bundle.risks,
        )
        codes = {finding.code for finding in DesignBundleValidator().validate(bundle)}
        self.assertTrue({"ORPHAN_ACCEPTANCE_CRITERION", "ARCHITECTURE_UNKNOWN_REQUIREMENT", "UX_UNKNOWN_REQUIREMENT"} <= codes)

    def test_must_requirement_needs_design_coverage(self):
        bundle = self.make_valid_bundle()
        bundle = DesignBundle(
            mission_id=bundle.mission_id,
            product_summary=bundle.product_summary,
            non_goals=bundle.non_goals,
            requirements=bundle.requirements,
            acceptance_criteria=bundle.acceptance_criteria,
            architecture_decisions=(),
            ux_flows=(),
            assumptions=bundle.assumptions,
            risks=bundle.risks,
        )
        codes = {finding.code for finding in DesignBundleValidator().validate(bundle)}
        self.assertIn("MUST_WITHOUT_DESIGN_COVERAGE", codes)

    def test_empty_risk_register_is_warning_not_blocker(self):
        bundle = self.make_valid_bundle()
        bundle = DesignBundle(
            mission_id=bundle.mission_id,
            product_summary=bundle.product_summary,
            non_goals=bundle.non_goals,
            requirements=bundle.requirements,
            acceptance_criteria=bundle.acceptance_criteria,
            architecture_decisions=bundle.architecture_decisions,
            ux_flows=bundle.ux_flows,
            assumptions=bundle.assumptions,
            risks=(),
        )
        findings = DesignBundleValidator().validate(bundle)
        self.assertEqual([item.code for item in findings], ["NO_RISKS_RECORDED"])
        self.assertTrue(DesignBundleValidator().is_build_ready(bundle))


if __name__ == "__main__":
    unittest.main()
