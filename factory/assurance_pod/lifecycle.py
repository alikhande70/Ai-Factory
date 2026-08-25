from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json

from factory.engineering_pod.integration import IntegrationManifest

from .contracts import AssuranceDecision


def integration_fingerprint(integration: IntegrationManifest) -> str:
    integration.validate()
    payload = {
        "mission_id": integration.mission_id,
        "package_order": integration.package_order,
        "artifacts": tuple(
            (item.artifact_name, item.owner_package_id) for item in integration.artifacts
        ),
        "changed_paths": integration.changed_paths,
        "verification_ids": integration.verification_ids,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AssuranceCycleRecord:
    cycle_id: str
    mission_id: str
    attempt: int
    subject_fingerprint: str
    decision_status: str
    blocking_finding_ids: tuple[str, ...]
    stale: bool = False

    def validate(self) -> None:
        if not self.cycle_id or not self.mission_id or not self.subject_fingerprint:
            raise ValueError("cycle identity and subject_fingerprint are required")
        if self.attempt < 1:
            raise ValueError("assurance attempt must be >= 1")
        if self.decision_status not in {"PASS", "CHANGES_REQUIRED"}:
            raise ValueError("invalid assurance cycle decision_status")
        if self.decision_status == "PASS" and self.blocking_finding_ids:
            raise ValueError("PASS cycle cannot contain blocking findings")
        if self.decision_status == "CHANGES_REQUIRED" and not self.blocking_finding_ids:
            raise ValueError("CHANGES_REQUIRED cycle requires blocking findings")


@dataclass(frozen=True)
class RemediationRequest:
    mission_id: str
    from_cycle_id: str
    subject_fingerprint: str
    blocking_finding_ids: tuple[str, ...]

    def validate(self) -> None:
        if not self.mission_id or not self.from_cycle_id or not self.subject_fingerprint:
            raise ValueError("remediation request identity is required")
        if not self.blocking_finding_ids:
            raise ValueError("remediation request requires blocking findings")


class AssuranceLifecycle:
    """Deterministic freshness, bounded re-review and release-readiness gate."""

    def __init__(self, *, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts

    def record(
        self,
        *,
        cycle_id: str,
        integration: IntegrationManifest,
        decision: AssuranceDecision,
        attempt: int = 1,
    ) -> AssuranceCycleRecord:
        decision.validate()
        if decision.mission_id != integration.mission_id:
            raise ValueError("assurance decision/integration mission mismatch")
        record = AssuranceCycleRecord(
            cycle_id=cycle_id,
            mission_id=integration.mission_id,
            attempt=attempt,
            subject_fingerprint=integration_fingerprint(integration),
            decision_status=decision.status,
            blocking_finding_ids=decision.blocking_finding_ids,
        )
        record.validate()
        return record

    def remediation_request(self, record: AssuranceCycleRecord) -> RemediationRequest:
        record.validate()
        if record.stale:
            raise RuntimeError("cannot remediate from stale assurance")
        if record.decision_status != "CHANGES_REQUIRED":
            raise RuntimeError("remediation requires CHANGES_REQUIRED")
        request = RemediationRequest(
            mission_id=record.mission_id,
            from_cycle_id=record.cycle_id,
            subject_fingerprint=record.subject_fingerprint,
            blocking_finding_ids=record.blocking_finding_ids,
        )
        request.validate()
        return request

    def re_review(
        self,
        *,
        previous: AssuranceCycleRecord,
        corrected_integration: IntegrationManifest,
        decision: AssuranceDecision,
        cycle_id: str,
    ) -> tuple[AssuranceCycleRecord, AssuranceCycleRecord]:
        previous.validate()
        if previous.stale:
            raise RuntimeError("previous assurance is already stale")
        if previous.decision_status != "CHANGES_REQUIRED":
            raise RuntimeError("re-review requires a prior blocking decision")
        if previous.attempt >= self.max_attempts:
            raise RuntimeError("assurance remediation budget exhausted")
        if corrected_integration.mission_id != previous.mission_id:
            raise ValueError("corrected integration mission mismatch")
        new_fingerprint = integration_fingerprint(corrected_integration)
        if new_fingerprint == previous.subject_fingerprint:
            raise RuntimeError("assurance remediation made no subject change")
        stale_previous = replace(previous, stale=True)
        current = self.record(
            cycle_id=cycle_id,
            integration=corrected_integration,
            decision=decision,
            attempt=previous.attempt + 1,
        )
        return stale_previous, current

    def assert_release_ready(
        self,
        *,
        record: AssuranceCycleRecord,
        integration: IntegrationManifest,
    ) -> None:
        record.validate()
        if record.stale:
            raise RuntimeError("stale assurance cannot release")
        if record.decision_status != "PASS":
            raise RuntimeError("blocking assurance findings prevent release")
        if record.subject_fingerprint != integration_fingerprint(integration):
            raise RuntimeError("assurance subject changed after review")
