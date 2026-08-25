import json
import tempfile
import unittest

from examples.phase4_booking_app import BookingForm, BookingRepository, BookingService, submit_booking
from factory.design_pod import AcceptanceCriterion, ArchitectureDecision, DesignBundle, ProductRequirement, UXFlow
from factory.engineering_pod import (
    DesignToEngineeringFixturePlanner,
    EngineeringPodCoordinator,
    EvidenceManifest,
    FixturePackageSpec,
    VerificationResult,
)
from factory.runtime.catalog import SQLiteRuntimeCatalog


def booking_design() -> DesignBundle:
    return DesignBundle(
        mission_id="MISSION-PHASE4-QUALIFICATION",
        product_summary="Controlled booking application",
        non_goals=("production deployment",),
        requirements=(
            ProductRequirement("REQ-UI", "User can submit a booking", "MUST"),
            ProductRequirement("REQ-DATA", "Booking is stored consistently", "MUST"),
        ),
        acceptance_criteria=(
            AcceptanceCriterion("AC-UI", "REQ-UI", "Booking form submits through service", "full-stack test"),
            AcceptanceCriterion("AC-DATA", "REQ-DATA", "Created booking can be read back", "full-stack test"),
        ),
        architecture_decisions=(
            ArchitectureDecision(
                "ADR-BOOKING",
                "Booking storage boundary",
                "Frontend adapter -> backend service -> transactional SQLite repository",
                "Small controlled evaluation with explicit persistence boundary",
                ("REQ-UI", "REQ-DATA"),
            ),
        ),
        ux_flows=(
            UXFlow(
                "UX-BOOK",
                "Create booking",
                "user",
                ("Enter customer name", "Choose slot", "Submit", "See booking identifier"),
                ("REQ-UI",),
            ),
        ),
        risks=("This fixture is evaluation-only and not a production booking product",),
    )


def booking_fixture() -> tuple[FixturePackageSpec, ...]:
    return (
        FixturePackageSpec(
            package_id="PKG-DB",
            discipline="DATABASE",
            requirement_ids=("REQ-DATA",),
            write_scopes=("examples/phase4_booking_app/db.py",),
            expected_artifacts=("booking-repository",),
            verification_methods=("full-stack test",),
            objective="Implement transactional booking persistence",
        ),
        FixturePackageSpec(
            package_id="PKG-BE",
            discipline="BACKEND",
            requirement_ids=("REQ-UI", "REQ-DATA"),
            depends_on=("PKG-DB",),
            write_scopes=("examples/phase4_booking_app/backend.py",),
            expected_artifacts=("booking-service",),
            verification_methods=("full-stack test",),
            objective="Implement validated booking service boundary",
        ),
        FixturePackageSpec(
            package_id="PKG-FE",
            discipline="FRONTEND",
            requirement_ids=("REQ-UI",),
            depends_on=("PKG-BE",),
            write_scopes=("examples/phase4_booking_app/frontend.py",),
            expected_artifacts=("booking-form-adapter",),
            verification_methods=("full-stack test",),
            objective="Implement booking form adapter",
        ),
    )


class ControlledWorker:
    def __init__(self, agent_id: str, discipline: str) -> None:
        self.agent_id = agent_id
        self.discipline = discipline

    def implement(self, *, design, package, workspace_id):
        return EvidenceManifest(
            package_id=package.package_id,
            changed_paths=package.write_scopes,
            produced_artifacts=package.expected_artifacts,
            verification_results=(
                VerificationResult(
                    verification_id=f"VER-{package.package_id}",
                    method="full-stack test",
                    status="PASS",
                    evidence_ref=f"ci://phase4-qualification/{workspace_id}",
                ),
            ),
        )


class Phase4QualificationTests(unittest.TestCase):
    def test_design_bundle_to_integrated_working_application(self):
        design = booking_design()
        planner = DesignToEngineeringFixturePlanner(booking_fixture())

        with tempfile.TemporaryDirectory() as directory:
            catalog = SQLiteRuntimeCatalog(f"{directory}/factory.db")
            coordinator = EngineeringPodCoordinator(
                planner=planner,
                workers=(
                    ControlledWorker("A05-FRONTEND", "FRONTEND"),
                    ControlledWorker("A06-BACKEND", "BACKEND"),
                    ControlledWorker("A07-DATABASE", "DATABASE"),
                ),
                catalog=catalog,
            )
            evidence, integration = coordinator.run_integrated(design=design)

            self.assertEqual(integration.package_order, ("PKG-DB", "PKG-BE", "PKG-FE"))
            self.assertEqual({item.package_id for item in evidence}, {"PKG-DB", "PKG-BE", "PKG-FE"})

            repository = BookingRepository(f"{directory}/booking.db")
            service = BookingService(repository)
            created = submit_booking(BookingForm(customer_name="Ada", slot="09:00"), service)
            loaded = service.get_booking(created.booking_id)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.customer_name, "Ada")
            self.assertEqual(loaded.slot, "09:00")

            stored = catalog.latest_artifact(design.mission_id, "engineering-integration-manifest")
            manifest = json.loads(stored["content_text"])
            self.assertEqual(tuple(manifest["package_order"]), integration.package_order)
            self.assertEqual(len(manifest["artifacts"]), 3)

    def test_fixture_rejects_unknown_design_requirement(self):
        invalid = FixturePackageSpec(
            package_id="PKG-X",
            discipline="BACKEND",
            requirement_ids=("REQ-NOT-IN-DESIGN",),
            write_scopes=("examples/phase4_booking_app/backend.py",),
            expected_artifacts=("x",),
            verification_methods=("full-stack test",),
        )
        planner = DesignToEngineeringFixturePlanner((invalid,))
        with self.assertRaisesRegex(ValueError, "unknown requirements"):
            planner.plan_engineering(design=booking_design())

    def test_frontend_validation_failure_does_not_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = BookingRepository(f"{directory}/booking.db")
            service = BookingService(repository)
            with self.assertRaisesRegex(ValueError, "customer_name is required"):
                submit_booking(BookingForm(customer_name="   ", slot="09:00"), service)
            self.assertIsNone(repository.get(1))


if __name__ == "__main__":
    unittest.main()
