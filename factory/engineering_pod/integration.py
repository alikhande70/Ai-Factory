from __future__ import annotations

from dataclasses import dataclass

from .contracts import EvidenceManifest, ImplementationWorkPackage
from .validator import EngineeringFinding, EngineeringPlanValidator


@dataclass(frozen=True)
class IntegratedArtifact:
    artifact_name: str
    owner_package_id: str


@dataclass(frozen=True)
class IntegrationManifest:
    mission_id: str
    package_order: tuple[str, ...]
    artifacts: tuple[IntegratedArtifact, ...]
    changed_paths: tuple[str, ...]
    verification_ids: tuple[str, ...]

    def validate(self) -> None:
        if not self.mission_id:
            raise ValueError("mission_id is required")
        if not self.package_order:
            raise ValueError("package_order cannot be empty")
        if len(self.package_order) != len(set(self.package_order)):
            raise ValueError("package_order cannot contain duplicates")
        if len(self.changed_paths) != len(set(self.changed_paths)):
            raise ValueError("integrated changed_paths cannot contain duplicates")
        if len(self.verification_ids) != len(set(self.verification_ids)):
            raise ValueError("verification_ids cannot contain duplicates")
        artifact_names = [item.artifact_name for item in self.artifacts]
        if len(artifact_names) != len(set(artifact_names)):
            raise ValueError("integrated artifacts require unique names")
        if any(not item.artifact_name or not item.owner_package_id for item in self.artifacts):
            raise ValueError("integrated artifact name and owner are required")


class EngineeringIntegrationValidator:
    """Build a deterministic integration manifest from validated package evidence."""

    def __init__(self, evidence_validator: EngineeringPlanValidator | None = None) -> None:
        self.evidence_validator = evidence_validator or EngineeringPlanValidator()

    def integrate(
        self,
        *,
        mission_id: str,
        packages: tuple[ImplementationWorkPackage, ...],
        evidence: tuple[EvidenceManifest, ...],
        package_order: tuple[str, ...],
    ) -> IntegrationManifest:
        if not mission_id:
            raise ValueError("mission_id is required")
        package_map = {item.package_id: item for item in packages}
        if len(package_map) != len(packages):
            raise ValueError("duplicate package IDs cannot be integrated")
        if any(item.mission_id != mission_id for item in packages):
            raise ValueError("all work packages must belong to the integration mission")
        if len(package_order) != len(set(package_order)) or set(package_order) != set(package_map):
            raise ValueError("package_order must contain every work package exactly once")

        evidence_map: dict[str, EvidenceManifest] = {}
        for item in evidence:
            if item.package_id in evidence_map:
                raise ValueError(f"duplicate evidence for package {item.package_id}")
            evidence_map[item.package_id] = item
        if set(evidence_map) != set(package_map):
            missing = sorted(set(package_map) - set(evidence_map))
            unknown = sorted(set(evidence_map) - set(package_map))
            raise ValueError(f"integration evidence mismatch: missing={missing}, unknown={unknown}")

        position = {package_id: index for index, package_id in enumerate(package_order)}
        for package in packages:
            for dependency in package.depends_on:
                if dependency not in position:
                    raise ValueError(f"unknown dependency in integration: {dependency}")
                if position[dependency] >= position[package.package_id]:
                    raise ValueError(
                        f"dependency {dependency} must integrate before {package.package_id}"
                    )

        artifact_owner: dict[str, str] = {}
        path_owner: dict[str, str] = {}
        verification_ids: list[str] = []
        changed_paths: list[str] = []

        for package_id in package_order:
            package = package_map[package_id]
            manifest = evidence_map[package_id]
            blockers = tuple(
                finding
                for finding in self.evidence_validator.validate_evidence(package=package, evidence=manifest)
                if finding.severity == "BLOCKING"
            )
            if blockers:
                codes = ",".join(finding.code for finding in blockers)
                raise ValueError(f"package evidence cannot integrate:{package_id}:{codes}")

            for artifact in manifest.produced_artifacts:
                previous = artifact_owner.get(artifact)
                if previous is not None and previous != package_id:
                    raise ValueError(
                        f"ambiguous artifact ownership:{artifact}:{previous}:{package_id}"
                    )
                artifact_owner[artifact] = package_id

            for path in manifest.changed_paths:
                previous = path_owner.get(path)
                if previous is not None and previous != package_id:
                    raise ValueError(
                        f"same path changed by multiple packages:{path}:{previous}:{package_id}"
                    )
                path_owner[path] = package_id
                changed_paths.append(path)

            for result in manifest.verification_results:
                if result.verification_id in verification_ids:
                    raise ValueError(f"duplicate verification ID:{result.verification_id}")
                verification_ids.append(result.verification_id)

        integrated = IntegrationManifest(
            mission_id=mission_id,
            package_order=package_order,
            artifacts=tuple(
                IntegratedArtifact(name, owner)
                for name, owner in sorted(artifact_owner.items())
            ),
            changed_paths=tuple(changed_paths),
            verification_ids=tuple(verification_ids),
        )
        integrated.validate()
        return integrated
