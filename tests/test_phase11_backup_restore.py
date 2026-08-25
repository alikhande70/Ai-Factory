from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from factory.runtime.backup import SQLiteBackupManager
from factory.runtime.catalog import SQLiteRuntimeCatalog
from factory.runtime.mission_scope import MissionScopedCatalog


class Phase11BackupRestoreTests(unittest.TestCase):
    def _seed_runtime(self, path: Path) -> None:
        catalog = SQLiteRuntimeCatalog(path)
        scoped = MissionScopedCatalog(catalog, "MISSION-BACKUP")
        scoped.add_artifact(
            artifact_id="SPEC",
            content="canonical-version-1",
            created_by="A02",
        )
        scoped.set_budget(50)
        scoped.consume_budget(7)
        scoped.propose_action(
            proposal_id="APPROVAL-1",
            action_type="PRODUCTION_DEPLOY",
            target="service-a",
            protected=True,
        )

    def test_online_backup_restores_exact_canonical_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "runtime.db"
            backup = root / "backups" / "runtime.snapshot.db"
            restored = root / "restored.db"
            self._seed_runtime(source)

            manifest = SQLiteBackupManager(source).create_backup(backup)
            self.assertEqual(manifest.sqlite_integrity, "ok")
            self.assertEqual(len(manifest.sha256), 64)
            self.assertTrue(Path(f"{backup}.manifest.json").exists())

            SQLiteBackupManager.restore_backup(backup, restored)
            restored_catalog = SQLiteRuntimeCatalog(restored)
            scoped = MissionScopedCatalog(restored_catalog, "MISSION-BACKUP")
            self.assertEqual(
                scoped.latest_artifact("SPEC")["content_text"],
                "canonical-version-1",
            )
            self.assertEqual(scoped.consume_budget(1), (8, 50))
            self.assertEqual(scoped.approval_status("APPROVAL-1"), "PENDING")

    def test_tampered_backup_is_rejected_without_replacing_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "runtime.db"
            backup = root / "runtime.snapshot.db"
            destination = root / "destination.db"
            self._seed_runtime(source)
            SQLiteBackupManager(source).create_backup(backup)

            with sqlite3.connect(destination) as connection:
                connection.execute("CREATE TABLE sentinel(value TEXT NOT NULL)")
                connection.execute("INSERT INTO sentinel VALUES ('preserve-me')")

            raw = bytearray(backup.read_bytes())
            raw[-1] ^= 0x01
            backup.write_bytes(raw)

            with self.assertRaisesRegex(ValueError, "hash does not match"):
                SQLiteBackupManager.restore_backup(
                    backup, destination, overwrite=True
                )

            with sqlite3.connect(destination) as connection:
                value = connection.execute("SELECT value FROM sentinel").fetchone()[0]
            self.assertEqual(value, "preserve-me")

    def test_restore_requires_explicit_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "runtime.db"
            backup = root / "runtime.snapshot.db"
            destination = root / "destination.db"
            self._seed_runtime(source)
            SQLiteBackupManager(source).create_backup(backup)
            destination.write_bytes(b"existing")

            with self.assertRaises(FileExistsError):
                SQLiteBackupManager.restore_backup(backup, destination)
            self.assertEqual(destination.read_bytes(), b"existing")

    def test_manifest_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "runtime.db"
            backup = root / "runtime.snapshot.db"
            self._seed_runtime(source)
            SQLiteBackupManager(source).create_backup(backup)
            manifest_path = Path(f"{backup}.manifest.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "hash does not match"):
                SQLiteBackupManager.restore_backup(backup, root / "restored.db")

    def test_backup_does_not_overwrite_existing_snapshot_without_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "runtime.db"
            backup = root / "runtime.snapshot.db"
            self._seed_runtime(source)
            manager = SQLiteBackupManager(source)
            manager.create_backup(backup)
            original_hash = backup.read_bytes()

            with self.assertRaises(FileExistsError):
                manager.create_backup(backup)
            self.assertEqual(backup.read_bytes(), original_hash)


if __name__ == "__main__":
    unittest.main()
