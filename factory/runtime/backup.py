from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile


@dataclass(frozen=True)
class BackupManifest:
    source_name: str
    created_at: str
    sha256: str
    size_bytes: int
    sqlite_integrity: str
    format_version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "format_version": self.format_version,
            "source_name": self.source_name,
            "created_at": self.created_at,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "sqlite_integrity": self.sqlite_integrity,
        }


class SQLiteBackupManager:
    """Fail-closed online backup/restore for canonical SQLite runtime state.

    Backups use SQLite's online backup API rather than file copying so WAL state is
    captured consistently. A sidecar manifest binds the backup to an exact SHA-256
    and size. Restore verifies the manifest, SQLite integrity, and a staged copy
    before atomically replacing the destination.
    """

    def __init__(self, source_path: str | Path) -> None:
        self.source_path = Path(source_path)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _integrity_check(path: Path) -> str:
        connection = sqlite3.connect(str(path))
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
        if row is None:
            raise ValueError("sqlite integrity_check returned no result")
        return str(row[0])

    def create_backup(
        self,
        backup_path: str | Path,
        *,
        manifest_path: str | Path | None = None,
        overwrite: bool = False,
    ) -> BackupManifest:
        if not self.source_path.exists():
            raise FileNotFoundError(self.source_path)
        destination = Path(backup_path)
        manifest_destination = (
            Path(manifest_path)
            if manifest_path is not None
            else Path(f"{destination}.manifest.json")
        )
        if not overwrite and (destination.exists() or manifest_destination.exists()):
            raise FileExistsError("backup or manifest already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        manifest_destination.parent.mkdir(parents=True, exist_ok=True)

        source = sqlite3.connect(str(self.source_path))
        target = sqlite3.connect(str(destination))
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

        integrity = self._integrity_check(destination)
        if integrity.lower() != "ok":
            destination.unlink(missing_ok=True)
            raise ValueError(f"backup sqlite integrity failed: {integrity}")

        manifest = BackupManifest(
            source_name=self.source_path.name,
            created_at=datetime.now(timezone.utc).isoformat(),
            sha256=self._sha256(destination),
            size_bytes=destination.stat().st_size,
            sqlite_integrity=integrity,
        )
        payload = json.dumps(
            manifest.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        manifest_destination.write_text(payload, encoding="utf-8")
        return manifest

    @classmethod
    def restore_backup(
        cls,
        backup_path: str | Path,
        destination_path: str | Path,
        *,
        manifest_path: str | Path | None = None,
        overwrite: bool = False,
    ) -> BackupManifest:
        backup = Path(backup_path)
        destination = Path(destination_path)
        manifest_source = (
            Path(manifest_path)
            if manifest_path is not None
            else Path(f"{backup}.manifest.json")
        )
        if not backup.exists():
            raise FileNotFoundError(backup)
        if not manifest_source.exists():
            raise FileNotFoundError(manifest_source)
        if destination.exists() and not overwrite:
            raise FileExistsError(destination)

        raw = json.loads(manifest_source.read_text(encoding="utf-8"))
        required = {
            "format_version",
            "source_name",
            "created_at",
            "sha256",
            "size_bytes",
            "sqlite_integrity",
        }
        if set(raw) != required or raw["format_version"] != 1:
            raise ValueError("unsupported or invalid backup manifest")
        actual_size = backup.stat().st_size
        if int(raw["size_bytes"]) != actual_size:
            raise ValueError("backup size does not match manifest")
        actual_hash = cls._sha256(backup)
        if str(raw["sha256"]) != actual_hash:
            raise ValueError("backup hash does not match manifest")
        integrity = cls._integrity_check(backup)
        if integrity.lower() != "ok":
            raise ValueError(f"backup sqlite integrity failed: {integrity}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, staged_name = tempfile.mkstemp(
            prefix=f".{destination.name}.restore-", dir=str(destination.parent)
        )
        os.close(fd)
        staged = Path(staged_name)
        try:
            source = sqlite3.connect(str(backup))
            target = sqlite3.connect(str(staged))
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
            staged_integrity = cls._integrity_check(staged)
            if staged_integrity.lower() != "ok":
                raise ValueError(f"staged restore integrity failed: {staged_integrity}")
            os.replace(staged, destination)
        finally:
            staged.unlink(missing_ok=True)

        return BackupManifest(
            source_name=str(raw["source_name"]),
            created_at=str(raw["created_at"]),
            sha256=str(raw["sha256"]),
            size_bytes=int(raw["size_bytes"]),
            sqlite_integrity=str(raw["sqlite_integrity"]),
            format_version=int(raw["format_version"]),
        )
