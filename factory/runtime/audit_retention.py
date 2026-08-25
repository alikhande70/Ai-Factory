from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from factory.control_plane.ledger import AuditEvent, AuditLedger
from .sqlite_store import SQLiteAuditLedger


ARCHIVE_FORMAT_VERSION = 1


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("audit timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class AuditRetentionPolicy:
    archive_after_days: int

    def __post_init__(self) -> None:
        if self.archive_after_days < 1:
            raise ValueError("archive_after_days must be >= 1")

    def cutoff(self, *, now: datetime) -> datetime:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        from datetime import timedelta

        return now.astimezone(timezone.utc) - timedelta(days=self.archive_after_days)


@dataclass(frozen=True)
class AuditArchiveManifest:
    format_version: int
    archive_file: str
    created_at: str
    cutoff_at: str
    event_count: int
    first_sequence: int
    last_sequence: int
    first_previous_hash: str
    last_event_hash: str
    archive_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditArchiveManager:
    """Creates and verifies non-destructive, hash-bound audit archives.

    Archives always contain a contiguous prefix beginning at sequence 1. This makes
    each archive independently verifiable from GENESIS and avoids inventing a second
    trust anchor before an archive-anchor/recovery protocol is qualified.

    This component deliberately does not delete canonical audit rows.
    """

    def __init__(self, ledger: SQLiteAuditLedger) -> None:
        self.ledger = ledger

    def create_archive(
        self,
        *,
        policy: AuditRetentionPolicy,
        archive_path: str | Path,
        manifest_path: str | Path,
        now: datetime,
        overwrite: bool = False,
    ) -> AuditArchiveManifest:
        archive = Path(archive_path)
        manifest = Path(manifest_path)
        if (archive.exists() or manifest.exists()) and not overwrite:
            raise FileExistsError("audit archive or manifest already exists")

        self.ledger.verify_integrity()
        cutoff = policy.cutoff(now=now)
        all_events = self.ledger.events()
        eligible: list[AuditEvent] = []
        for event in all_events:
            if _parse_time(event.created_at) <= cutoff:
                eligible.append(event)
            else:
                break

        if not eligible:
            raise RuntimeError("no_audit_events_eligible_for_archive")

        # Eligible events must be a prefix. If any later event is older than cutoff,
        # timestamps are non-monotonic and retention decisions are ambiguous.
        if any(_parse_time(event.created_at) <= cutoff for event in all_events[len(eligible) :]):
            raise RuntimeError("non_monotonic_audit_timestamps")

        verified = AuditLedger.from_events(eligible)
        events_payload = [asdict(event) for event in verified.events()]
        archive_payload = {
            "format_version": ARCHIVE_FORMAT_VERSION,
            "cutoff_at": cutoff.isoformat(),
            "events": events_payload,
        }
        encoded = (_canonical_json(archive_payload) + "\n").encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()

        archive.parent.mkdir(parents=True, exist_ok=True)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(encoded)

        created_at = now.astimezone(timezone.utc).isoformat()
        result = AuditArchiveManifest(
            format_version=ARCHIVE_FORMAT_VERSION,
            archive_file=archive.name,
            created_at=created_at,
            cutoff_at=cutoff.isoformat(),
            event_count=len(eligible),
            first_sequence=eligible[0].sequence,
            last_sequence=eligible[-1].sequence,
            first_previous_hash=eligible[0].previous_hash,
            last_event_hash=eligible[-1].event_hash,
            archive_sha256=digest,
        )
        manifest.write_text(_canonical_json(result.to_dict()) + "\n", encoding="utf-8")
        return result

    @staticmethod
    def verify_archive(*, archive_path: str | Path, manifest_path: str | Path) -> AuditArchiveManifest:
        archive = Path(archive_path)
        manifest_file = Path(manifest_path)
        raw_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        result = AuditArchiveManifest(**raw_manifest)

        if result.format_version != ARCHIVE_FORMAT_VERSION:
            raise ValueError("unsupported audit archive format")
        if result.archive_file != archive.name:
            raise ValueError("audit archive filename mismatch")

        encoded = archive.read_bytes()
        digest = hashlib.sha256(encoded).hexdigest()
        if digest != result.archive_sha256:
            raise ValueError("audit archive hash mismatch")

        payload = json.loads(encoded.decode("utf-8"))
        if payload.get("format_version") != ARCHIVE_FORMAT_VERSION:
            raise ValueError("audit archive payload version mismatch")
        if payload.get("cutoff_at") != result.cutoff_at:
            raise ValueError("audit archive cutoff mismatch")

        event_dicts = payload.get("events")
        if not isinstance(event_dicts, list) or not event_dicts:
            raise ValueError("audit archive must contain events")
        events = tuple(AuditEvent(**item) for item in event_dicts)
        verified = AuditLedger.from_events(events)

        if result.event_count != len(events):
            raise ValueError("audit archive event count mismatch")
        if result.first_sequence != events[0].sequence or result.first_sequence != 1:
            raise ValueError("audit archive must start at sequence 1")
        if result.last_sequence != events[-1].sequence:
            raise ValueError("audit archive last sequence mismatch")
        if result.first_previous_hash != "GENESIS" or events[0].previous_hash != "GENESIS":
            raise ValueError("audit archive does not start at GENESIS")
        if result.last_event_hash != events[-1].event_hash:
            raise ValueError("audit archive last hash mismatch")

        # Keep the verified ledger live long enough to make the intent explicit.
        verified.verify_integrity()
        return result
