from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from factory.control_plane.graph import TaskNode, validate_graph
from factory.control_plane.ledger import AuditEvent, AuditLedger
from factory.control_plane.runner import MissionRunner


def _canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class SQLiteAuditLedger:
    """Durable append-only audit ledger backed by SQLite.

    Each append runs under BEGIN IMMEDIATE so sequence/hash-chain selection and
    insertion are one transaction. The database is the source of truth; workers
    never write it directly.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    mission_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_mission_sequence "
                "ON audit_events(mission_id, sequence)"
            )

    def append(
        self,
        *,
        event_id: str,
        mission_id: str,
        actor_id: str,
        event_type: str,
        payload: dict,
        created_at: str | None = None,
    ) -> AuditEvent:
        if not mission_id or not actor_id or not event_type:
            raise ValueError("mission_id, actor_id and event_type are required")
        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT 1 FROM audit_events WHERE event_id = ?", (event_id,)
                ).fetchone():
                    raise ValueError(f"duplicate event id: {event_id}")
                last = connection.execute(
                    "SELECT sequence, event_hash FROM audit_events "
                    "ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                sequence = 1 if last is None else int(last["sequence"]) + 1
                previous_hash = "GENESIS" if last is None else str(last["event_hash"])
                unsigned = {
                    "sequence": sequence,
                    "event_id": event_id,
                    "mission_id": mission_id,
                    "actor_id": actor_id,
                    "event_type": event_type,
                    "payload": payload,
                    "created_at": timestamp,
                    "previous_hash": previous_hash,
                }
                event_hash = hashlib.sha256(
                    _canonical_json(unsigned).encode("utf-8")
                ).hexdigest()
                connection.execute(
                    "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        sequence,
                        event_id,
                        mission_id,
                        actor_id,
                        event_type,
                        _canonical_json(payload),
                        timestamp,
                        previous_hash,
                        event_hash,
                    ),
                )
                connection.commit()
                return AuditEvent(event_hash=event_hash, **unsigned)
            except Exception:
                connection.rollback()
                raise

    def events(self, mission_id: str | None = None) -> tuple[AuditEvent, ...]:
        query = "SELECT * FROM audit_events"
        params: tuple[str, ...] = ()
        if mission_id is not None:
            query += " WHERE mission_id = ?"
            params = (mission_id,)
        query += " ORDER BY sequence"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(
            AuditEvent(
                sequence=int(row["sequence"]),
                event_id=str(row["event_id"]),
                mission_id=str(row["mission_id"]),
                actor_id=str(row["actor_id"]),
                event_type=str(row["event_type"]),
                payload=json.loads(str(row["payload_json"])),
                created_at=str(row["created_at"]),
                previous_hash=str(row["previous_hash"]),
                event_hash=str(row["event_hash"]),
            )
            for row in rows
        )

    def verify_integrity(self) -> None:
        AuditLedger.from_events(self.events())


class SQLiteMissionStore:
    """Persist mission graph definitions and restore runners from the audit log."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.ledger = SQLiteAuditLedger(path)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS missions "
                "(mission_id TEXT PRIMARY KEY, created_at TEXT NOT NULL)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_tasks (
                    mission_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    dependencies_json TEXT NOT NULL,
                    write_scopes_json TEXT NOT NULL,
                    PRIMARY KEY (mission_id, task_id),
                    FOREIGN KEY (mission_id) REFERENCES missions(mission_id)
                )
                """
            )

    def create_runner(
        self, mission_id: str, task_nodes: Iterable[TaskNode]
    ) -> MissionRunner:
        nodes = tuple(task_nodes)
        validate_graph(list(nodes))
        if not mission_id or not nodes:
            raise ValueError("mission_id and at least one task are required")
        with closing(sqlite3.connect(self.path)) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO missions(mission_id, created_at) VALUES (?, ?)",
                    (mission_id, datetime.now(timezone.utc).isoformat()),
                )
                connection.executemany(
                    "INSERT INTO mission_tasks VALUES (?, ?, ?, ?)",
                    [
                        (
                            mission_id,
                            node.task_id,
                            _canonical_json({"items": list(node.dependencies)}),
                            _canonical_json({"items": list(node.write_scopes)}),
                        )
                        for node in nodes
                    ],
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError(f"mission already exists: {mission_id}") from exc
        return MissionRunner(
            mission_id,
            [node.task_id for node in nodes],
            ledger=self.ledger,
            task_nodes=nodes,
        )

    def restore_runner(self, mission_id: str) -> MissionRunner:
        nodes = self._load_nodes(mission_id)
        all_events = self.ledger.events()
        replayed = MissionRunner.replay(
            mission_id,
            [node.task_id for node in nodes],
            all_events,
            task_nodes=nodes,
        )
        # Replay used a verified in-memory ledger. Future appends go to the same
        # durable chain that was just verified.
        replayed.ledger = self.ledger
        return replayed

    def _load_nodes(self, mission_id: str) -> tuple[TaskNode, ...]:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            mission = connection.execute(
                "SELECT 1 FROM missions WHERE mission_id = ?", (mission_id,)
            ).fetchone()
            if mission is None:
                raise KeyError(f"unknown mission: {mission_id}")
            rows = connection.execute(
                "SELECT * FROM mission_tasks WHERE mission_id = ? ORDER BY task_id",
                (mission_id,),
            ).fetchall()
        return tuple(
            TaskNode(
                str(row["task_id"]),
                tuple(json.loads(str(row["dependencies_json"]))["items"]),
                tuple(json.loads(str(row["write_scopes_json"]))["items"]),
            )
            for row in rows
        )
