from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
from typing import Mapping

from .contracts import OrganizationalMemoryEntry


MEMORY_SCOPES = frozenset({"MISSION", "GLOBAL"})
MEMORY_STATUSES = frozenset({"ACTIVE", "SUPERSEDED", "DEPRECATED"})


@dataclass(frozen=True)
class MemoryRecord:
    entry: OrganizationalMemoryEntry
    scope: str
    scope_mission_id: str | None
    status: str
    superseded_by: str | None = None

    def validate(self) -> None:
        self.entry.validate()
        if self.scope not in MEMORY_SCOPES:
            raise ValueError(f"unknown memory scope:{self.scope}")
        if self.status not in MEMORY_STATUSES:
            raise ValueError(f"unknown memory status:{self.status}")
        if self.scope == "MISSION" and self.scope_mission_id != self.entry.mission_id:
            raise ValueError("mission-scoped memory must be bound to its source mission")
        if self.scope == "GLOBAL" and self.scope_mission_id is not None:
            raise ValueError("global memory cannot carry a mission visibility binding")
        if self.status == "SUPERSEDED" and not self.superseded_by:
            raise ValueError("superseded memory requires replacement id")
        if self.superseded_by == self.entry.memory_id:
            raise ValueError("memory cannot supersede itself")


class SQLiteOrganizationalMemoryStore:
    """Durable append-audited memory. Existing entries are never destructively rewritten."""

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_entries(
                memory_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                scope TEXT NOT NULL,
                scope_mission_id TEXT,
                source_hash TEXT NOT NULL,
                fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory_events(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                FOREIGN KEY(memory_id) REFERENCES memory_entries(memory_id)
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _canonical(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _last_hash(self) -> str:
        row = self._conn.execute("SELECT event_hash FROM memory_events ORDER BY seq DESC LIMIT 1").fetchone()
        return row["event_hash"] if row else "GENESIS"

    def _append_event(self, memory_id: str, event_type: str, payload: Mapping[str, object]) -> None:
        prev_hash = self._last_hash()
        encoded = self._canonical(payload)
        material = "\n".join((prev_hash, memory_id, event_type, encoded))
        event_hash = "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()
        self._conn.execute(
            "INSERT INTO memory_events(memory_id,event_type,payload,prev_hash,event_hash) VALUES(?,?,?,?,?)",
            (memory_id, event_type, encoded, prev_hash, event_hash),
        )

    def promote(
        self,
        entry: OrganizationalMemoryEntry,
        *,
        scope: str,
        observed_source_hash: str,
    ) -> MemoryRecord:
        entry.validate()
        if observed_source_hash != entry.source_hash:
            raise RuntimeError("source hash changed since review; memory promotion rejected")
        record = MemoryRecord(
            entry=entry,
            scope=scope,
            scope_mission_id=entry.mission_id if scope == "MISSION" else None,
            status="ACTIVE",
        )
        record.validate()
        payload = asdict(entry)
        with self._conn:
            self._conn.execute(
                "INSERT INTO memory_entries(memory_id,payload,scope,scope_mission_id,source_hash,fingerprint) VALUES(?,?,?,?,?,?)",
                (
                    entry.memory_id,
                    self._canonical(payload),
                    record.scope,
                    record.scope_mission_id,
                    entry.source_hash,
                    entry.fingerprint,
                ),
            )
            self._append_event(entry.memory_id, "PROMOTED", {"scope": record.scope})
        return record

    def _status(self, memory_id: str) -> tuple[str, str | None]:
        rows = self._conn.execute(
            "SELECT event_type,payload FROM memory_events WHERE memory_id=? ORDER BY seq", (memory_id,)
        ).fetchall()
        if not rows:
            raise KeyError(memory_id)
        status = "ACTIVE"
        replacement = None
        for row in rows:
            payload = json.loads(row["payload"])
            if row["event_type"] == "DEPRECATED":
                status = "DEPRECATED"
                replacement = None
            elif row["event_type"] == "SUPERSEDED":
                status = "SUPERSEDED"
                replacement = str(payload["replacement_id"])
        return status, replacement

    def _decode_entry(self, row: sqlite3.Row) -> OrganizationalMemoryEntry:
        data = json.loads(row["payload"])
        data["evidence_refs"] = tuple(data["evidence_refs"])
        entry = OrganizationalMemoryEntry(**data)
        entry.validate()
        return entry

    def recall(
        self,
        memory_id: str,
        *,
        mission_id: str | None,
        observed_source_hashes: Mapping[str, str],
    ) -> MemoryRecord:
        row = self._conn.execute("SELECT * FROM memory_entries WHERE memory_id=?", (memory_id,)).fetchone()
        if row is None:
            raise KeyError(memory_id)
        entry = self._decode_entry(row)
        observed = observed_source_hashes.get(entry.source_ref)
        if observed != entry.source_hash:
            raise RuntimeError("memory source integrity could not be verified")
        if row["scope"] == "MISSION" and mission_id != row["scope_mission_id"]:
            raise PermissionError("mission-scoped memory is not visible to this mission")
        status, replacement = self._status(memory_id)
        return MemoryRecord(entry, row["scope"], row["scope_mission_id"], status, replacement)

    def supersede(self, memory_id: str, replacement_id: str) -> None:
        if memory_id == replacement_id:
            raise ValueError("memory cannot supersede itself")
        if self._conn.execute("SELECT 1 FROM memory_entries WHERE memory_id=?", (replacement_id,)).fetchone() is None:
            raise KeyError(replacement_id)
        status, _ = self._status(memory_id)
        if status != "ACTIVE":
            raise RuntimeError("only active memory can be superseded")
        with self._conn:
            self._append_event(memory_id, "SUPERSEDED", {"replacement_id": replacement_id})

    def deprecate(self, memory_id: str, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("deprecation reason is required")
        status, _ = self._status(memory_id)
        if status != "ACTIVE":
            raise RuntimeError("only active memory can be deprecated")
        with self._conn:
            self._append_event(memory_id, "DEPRECATED", {"reason": reason})

    def verify_audit_chain(self) -> bool:
        rows = self._conn.execute("SELECT * FROM memory_events ORDER BY seq").fetchall()
        expected_prev = "GENESIS"
        for row in rows:
            if row["prev_hash"] != expected_prev:
                return False
            material = "\n".join((row["prev_hash"], row["memory_id"], row["event_type"], row["payload"]))
            expected = "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()
            if expected != row["event_hash"]:
                return False
            expected_prev = row["event_hash"]
        return True
