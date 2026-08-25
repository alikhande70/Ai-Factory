import unittest

from factory.design_pod import (
    AcceptanceCriterion,
    ArchitectureDecision,
    ArchitectureDesignOutput,
    DesignPodCoordinator,
    ProductDesignOutput,
    ProductRequirement,
    RevisionRequest,
    UXDesignOutput,
    UXFlow,
)


class AmbiguousProductWorker:
    agent_id = "A02-PRODUCT"

    def __init__(self) -> None:
        self.revisions = 0

    def design_product(self, *, mission_id: str, objective: str) -> ProductDesignOutput:
        # A MUST requirement without a verification contract is intentionally
        # underspecified and must not pass directly into engineering.
        return ProductDesignOutput(
            product_summary=objective,
            non_goals=(),
            requirements=(ProductRequirement("REQ-LOGIN", "Users can sign in", "MUST"),),
            acceptance_criteria=(),
            risks=("authentication ambiguity",),
        )

    def revise_product(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
        request: RevisionRequest,
    ) -> ProductDesignOutput:
        self.revisions += 1
        self.assert_only_expected(request)
        return ProductDesignOutput(
            product_summary=objective,
            non_goals=(),
            requirements=product.requirements,
            acceptance_criteria=(
                AcceptanceCriterion(
                    "AC-LOGIN",
                    "REQ-LOGIN",
                    "Valid credentials create an authenticated session",
                    "integration test",
                ),
            ),
            risks=product.risks,
        )

    @staticmethod
    def assert_only_expected(request: RevisionRequest) -> None:
        codes = {finding.code for finding in request.findings}
        if codes != {"MUST_WITHOUT_ACCEPTANCE_CRITERION"}:
            raise AssertionError(f"unexpected product findings: {sorted(codes)}")


class ArchitectureWorker:
    agent_id = "A03-ARCH"

    def design_architecture(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
    ) -> ArchitectureDesignOutput:
        requirement_id = product.requirements[0].requirement_id
        return ArchitectureDesignOutput(
            decisions=(
                ArchitectureDecision(
                    "ADR-AUTH",
                    "Session boundary",
                    "Server-side session service",
                    "Centralize authentication state",
                    (requirement_id,),
                ),
            ),
            risks=("session fixation",),
        )


class ContradictoryUXWorker:
    agent_id = "A04-UX"

    def __init__(self) -> None:
        self.revisions = 0

    def design_ux(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
    ) -> UXDesignOutput:
        return UXDesignOutput(
            flows=(UXFlow("UX-AUTH", "Sign in", "user", ("Enter credentials",), ("REQ-NOT-REAL",)),),
            risks=("unclear recovery path",),
        )

    def revise_ux(
        self,
        *,
        mission_id: str,
        objective: str,
        product: ProductDesignOutput,
        ux: UXDesignOutput,
        request: RevisionRequest,
    ) -> UXDesignOutput:
        self.revisions += 1
        requirement_id = product.requirements[0].requirement_id
        return UXDesignOutput(
            flows=(
                UXFlow(
                    "UX-AUTH",
                    "Sign in",
                    "user",
                    ("Enter credentials", "Submit", "See authenticated state"),
                    (requirement_id,),
                ),
            ),
            risks=ux.risks,
        )


class Phase3DesignPodEvaluations(unittest.TestCase):
    def test_ambiguity_is_repaired_before_downstream_design_is_canonical(self):
        product = AmbiguousProductWorker()
        coordinator = DesignPodCoordinator(
            product_worker=product,
            architecture_worker=ArchitectureWorker(),
            ux_worker=ContradictoryUXWorker(),
            max_revision_rounds=2,
        )
        bundle = coordinator.run(mission_id="MISSION-AMBIGUITY", objective="Secure sign-in")
        self.assertEqual(product.revisions, 1)
        self.assertEqual(bundle.acceptance_criteria[0].requirement_id, "REQ-LOGIN")

    def test_cross_role_contradiction_is_routed_and_revalidated(self):
        ux = ContradictoryUXWorker()
        product = AmbiguousProductWorker()
        coordinator = DesignPodCoordinator(
            product_worker=product,
            architecture_worker=ArchitectureWorker(),
            ux_worker=ux,
            max_revision_rounds=3,
        )
        bundle = coordinator.run(mission_id="MISSION-CONTRADICTION", objective="Secure sign-in")
        self.assertEqual(product.revisions, 1)
        self.assertEqual(ux.revisions, 1)
        self.assertEqual(bundle.ux_flows[0].requirement_ids, ("REQ-LOGIN",))


if __name__ == "__main__":
    unittest.main()
