from __future__ import annotations

from dataclasses import dataclass

from factory.design_pod.contracts import DesignBundle

from .contracts import EvidenceManifest, ImplementationWorkPackage


@dataclass(frozen=True)
class EngineeringFinding:
    code: str
    severity: str
    message: str
    subject_id: str | None = None


def _normalize_scope(scope: str) -> str:
    value = scope.strip().replace("\\", "/").strip("/")
    if not value or value.startswith("..") or "/../" in f"/{value}/":
        raise ValueError(f"invalid write scope: {scope}")
    return value


def _path_in_scope(path: str, scope: str) -> bool:
    normalized_path = _normalize_scope(path)
    normalized_scope = _normalize_scope(scope)
    return normalized_path == normalized_scope or normalized_path.startswith(f"{normalized_scope}/")


class EngineeringPlanValidator:
    """Deterministic guardrails between DesignBundle and implementation work."""

    def validate(
        self,
        *,
        design: DesignBundle,
        packages: tuple[ImplementationWorkPackage, ...],
    ) -> tuple[EngineeringFinding, ...]:
        design.validate()
        findings: list[EngineeringFinding] = []
        requirement_ids = {item.requirement_id for item in design.requirements}
        must_ids = {item.requirement_id for item in design.requirements if item.priority == "MUST"}

        package_ids = [package.package_id for package in packages]
        package_id_set = set(package_ids)
        if len(package_ids) != len(package_id_set):
            findings.append(EngineeringFinding("DUPLICATE_PACKAGE_ID", "BLOCKING", "package IDs must be unique"))

        for package in packages:
            try:
                package.validate()
            except ValueError as exc:
                findings.append(
                    EngineeringFinding("INVALID_PACKAGE_CONTRACT", "BLOCKING", str(exc), package.package_id)
                )
                continue

            for requirement_id in package.requirement_ids:
                if requirement_id not in requirement_ids:
                    findings.append(
                        EngineeringFinding(
                            "PACKAGE_UNKNOWN_REQUIREMENT",
                            "BLOCKING",
                            f"package references unknown requirement {requirement_id}",
                            package.package_id,
                        )
                    )
            for dependency in package.depends_on:
                if dependency not in package_id_set:
                    findings.append(
                        EngineeringFinding(
                            "PACKAGE_UNKNOWN_DEPENDENCY",
                            "BLOCKING",
                            f"package depends on unknown package {dependency}",
                            package.package_id,
                        )
                    )
            for scope in package.write_scopes:
                try:
                    _normalize_scope(scope)
                except ValueError as exc:
                    findings.append(
                        EngineeringFinding("INVALID_WRITE_SCOPE", "BLOCKING", str(exc), package.package_id)
                    )

        graph = {package.package_id: set(package.depends_on) for package in packages}
        if self._has_cycle(graph):
            findings.append(EngineeringFinding("PACKAGE_DEPENDENCY_CYCLE", "BLOCKING", "package dependency graph contains a cycle"))

        covered = {requirement_id for package in packages for requirement_id in package.requirement_ids}
        for requirement_id in sorted(must_ids - covered):
            findings.append(
                EngineeringFinding(
                    "MUST_WITHOUT_ENGINEERING_OWNER",
                    "BLOCKING",
                    "MUST requirement is not assigned to an engineering work package",
                    requirement_id,
                )
            )

        for index, left in enumerate(packages):
            for right in packages[index + 1 :]:
                if not self._scopes_overlap(left.write_scopes, right.write_scopes):
                    continue
                if self._ordered(left.package_id, right.package_id, graph) or self._ordered(
                    right.package_id, left.package_id, graph
                ):
                    continue
                findings.append(
                    EngineeringFinding(
                        "UNORDERED_WRITE_SCOPE_CONFLICT",
                        "BLOCKING",
                        f"{left.package_id} and {right.package_id} overlap write scopes without dependency ordering",
                    )
                )

        return tuple(findings)

    def validate_evidence(
        self,
        *,
        package: ImplementationWorkPackage,
        evidence: EvidenceManifest,
    ) -> tuple[EngineeringFinding, ...]:
        package.validate()
        findings: list[EngineeringFinding] = []
        try:
            evidence.validate()
        except ValueError as exc:
            return (EngineeringFinding("INVALID_EVIDENCE_CONTRACT", "BLOCKING", str(exc), evidence.package_id),)

        if evidence.package_id != package.package_id:
            findings.append(
                EngineeringFinding("EVIDENCE_PACKAGE_MISMATCH", "BLOCKING", "evidence belongs to another package")
            )

        for path in evidence.changed_paths:
            try:
                allowed = any(_path_in_scope(path, scope) for scope in package.write_scopes)
            except ValueError as exc:
                findings.append(EngineeringFinding("INVALID_CHANGED_PATH", "BLOCKING", str(exc), path))
                continue
            if not allowed:
                findings.append(
                    EngineeringFinding(
                        "CHANGE_OUTSIDE_WRITE_SCOPE",
                        "BLOCKING",
                        f"changed path {path} is outside declared package scopes",
                        path,
                    )
                )

        missing_artifacts = set(package.expected_artifacts) - set(evidence.produced_artifacts)
        for artifact in sorted(missing_artifacts):
            findings.append(
                EngineeringFinding(
                    "EXPECTED_ARTIFACT_MISSING",
                    "BLOCKING",
                    f"expected artifact was not produced: {artifact}",
                    artifact,
                )
            )

        failed = [result for result in evidence.verification_results if result.status != "PASS"]
        for result in failed:
            findings.append(
                EngineeringFinding(
                    "VERIFICATION_FAILED",
                    "BLOCKING",
                    f"verification failed: {result.method}",
                    result.verification_id,
                )
            )

        executed_methods = {result.method for result in evidence.verification_results if result.status == "PASS"}
        for method in package.verification_methods:
            if method not in executed_methods:
                findings.append(
                    EngineeringFinding(
                        "REQUIRED_VERIFICATION_MISSING",
                        "BLOCKING",
                        f"required verification did not pass: {method}",
                        package.package_id,
                    )
                )

        return tuple(findings)

    @staticmethod
    def _has_cycle(graph: dict[str, set[str]]) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dependency in graph.get(node, set()):
                if dependency in graph and visit(dependency):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)

    @staticmethod
    def _ordered(before: str, after: str, graph: dict[str, set[str]]) -> bool:
        stack = list(graph.get(after, set()))
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current == before:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(graph.get(current, set()))
        return False

    @staticmethod
    def _scopes_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
        for left_scope in left:
            for right_scope in right:
                try:
                    left_normalized = _normalize_scope(left_scope)
                    right_normalized = _normalize_scope(right_scope)
                except ValueError:
                    continue
                if (
                    left_normalized == right_normalized
                    or left_normalized.startswith(f"{right_normalized}/")
                    or right_normalized.startswith(f"{left_normalized}/")
                ):
                    return True
        return False
