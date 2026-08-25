from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from factory.runtime.audit_retention import AuditArchiveManager, AuditRetentionPolicy
from factory.runtime.sqlite_store import SQLiteAuditLedger


class Phase11AuditRetentionTests(unittest.TestCase):
    def _ledger_with_events(self, path: Path, now: datetime) -> SQLiteAuditLedger:
        ledger = SQLiteAuditLedger(path)
        for index, age_days in enumerate((30, 20, 5), start=1):
            ledger.append(
                event_id=f"EV-{index}",
                mission_id="MISSION-001",
                actor_id="A11",
                event_type="TEST",
                payload={"n": index},
                created_at=(now - timedelta(days=age_days)).isoformat(),
            )
        return ledger

    def test_archive_is_contiguous_verified_prefix_and_source_is_not_deleted(self) -> None:
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = self._ledger_with_events(root / "runtime.db", now)
            manager = AuditArchiveManager(ledger)
            archive = root / "audit-prefix.json"
            manifest = root / "audit-prefix.manifest.json"

            result = manager.create_archive(
                policy=AuditRetentionPolicy(archive_after_days=10),
                archive_path=archive,
                manifest_path=manifest,
                now=now,
            )
            verified = manager.verify_archive(archive_path=archive, manifest_path=manifest)

            self.assertEqual(result.event_count, 2)
            self.assertEqual(verified.first_sequence, 1)
            self.assertEqual(verified.last_sequence, 2)
            self.assertEqual(verified.first_previous_hash, "GENESIS")
            self.assertEqual(len(ledger.events()), 3)
            ledger.verify_integrity()

    def test_tampered_archive_is_rejected(self) -> None:
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = AuditArchiveManager(self._ledger_with_events(root / "runtime.db", now))
            archive = root / "audit.json"
            manifest = root / "audit.manifest.json"
            manager.create_archive(
                policy=AuditRetentionPolicy(archive_after_days=10),
                archive_path=archive,
                manifest_path=manifest,
                now=now,
            )
            payload = json.loads(archive.read_text(encoding="utf-8"))
            payload["events"][0]["payload"]["n"] = 999
            archive.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                manager.verify_archive(archive_path=archive, manifest_path=manifest)

    def test_manifest_tamper_is_rejected(self) -> None:
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = AuditArchiveManager(self._ledger_with_events(root / "runtime.db", now))
            archive = root / "audit.json"
            manifest = root / "audit.manifest.json"
            manager.create_archive(
                policy=AuditRetentionPolicy(archive_after_days=10),
                archive_path=archive,
                manifest_path=manifest,
                now=now,
            )
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["last_event_hash"] = "0" * 64
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "last hash mismatch"):
                manager.verify_archive(archive_path=archive, manifest_path=manifest)

    def test_non_monotonic_timestamp_retention_fails_closed(self) -> None:
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = SQLiteAuditLedger(root / "runtime.db")
            times = (now - timedelta(days=30), now - timedelta(days=2), now - timedelta(days=20))
            for index, created_at in enumerate(times, start=1):
                ledger.append(
                    event_id=f"EV-{index}",
                    mission_id="MISSION-001",
                    actor_id="A11",
                    event_type="TEST",
                    payload={},
                    created_at=created_at.isoformat(),
                )
            manager = AuditArchiveManager(ledger)
            with self.assertRaisesRegex(RuntimeError, "non_monotonic_audit_timestamps"):
                manager.create_archive(
                    policy=AuditRetentionPolicy(archive_after_days=10),
                    archive_path=root / "audit.json",
                    manifest_path=root / "audit.manifest.json",
                    now=now,
                )

    def test_archive_requires_eligible_events_and_no_implicit_overwrite(self) -> None:
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = SQLiteAuditLedger(root / "runtime.db")
            ledger.append(
                event_id="EV-1",
                mission_id="MISSION-001",
                actor_id="A11",
                event_type="TEST",
                payload={},
                created_at=(now - timedelta(days=1)).isoformat(),
            )
            manager = AuditArchiveManager(ledger)
            with self.assertRaisesRegex(RuntimeError, "no_audit_events_eligible_for_archive"):
                manager.create_archive(
                    policy=AuditRetentionPolicy(archive_after_days=10),
                    archive_path=root / "audit.json",
                    manifest_path=root / "audit.manifest.json",
                    now=now,
                )

            old_ledger = self._ledger_with_events(root / "older.db", now)
            old_manager = AuditArchiveManager(old_ledger)
            archive = root / "old-audit.json"
            manifest = root / "old-audit.manifest.json"
            old_manager.create_archive(
                policy=AuditRetentionPolicy(archive_after_days=10),
                archive_path=archive,
                manifest_path=manifest,
                now=now,
            )
            with self.assertRaises(FileExistsError):
                old_manager.create_archive(
                    policy=AuditRetentionPolicy(archive_after_days=10),
                    archive_path=archive,
                    manifest_path=manifest,
                    now=now,
                )


if __name__ == "__main__":
    unittest.main()
