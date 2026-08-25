from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class SQLiteRuntimeCatalog:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK(active IN (0,1)),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    mission_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK(version > 0),
                    media_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    content_text TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (mission_id, artifact_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_artifacts_latest
                    ON artifacts(mission_id, artifact_id, version DESC);
                CREATE TABLE IF NOT EXISTS budgets (
                    mission_id TEXT PRIMARY KEY,
                    limit_units INTEGER NOT NULL CHECK(limit_units >= 0),
                    consumed_units INTEGER NOT NULL DEFAULT 0 CHECK(consumed_units >= 0),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    proposal_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    protected INTEGER NOT NULL CHECK(protected IN (0,1)),
                    status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','DENIED')),
                    decided_by TEXT,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                );
                """
            )

    def register_agent(
        self, agent_id: str, role: str, capabilities: tuple[str, ...], *, active: bool = True
    ) -> None:
        if not agent_id or not role:
            raise ValueError("agent_id and role are required")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO agents(agent_id, role, capabilities_json, active, updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    role=excluded.role,
                    capabilities_json=excluded.capabilities_json,
                    active=excluded.active,
                    updated_at=excluded.updated_at
                """,
                (agent_id, role, _json(sorted(set(capabilities))), int(active), _now()),
            )

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
        if row is None:
            raise KeyError(agent_id)
        return {
            "agent_id": str(row["agent_id"]),
            "role": str(row["role"]),
            "capabilities": tuple(json.loads(str(row["capabilities_json"]))),
            "active": bool(row["active"]),
        }

    def add_artifact(
        self,
        *,
        mission_id: str,
        artifact_id: str,
        content: str,
        created_by: str,
        media_type: str = "text/plain",
    ) -> dict[str, Any]:
        if not mission_id or not artifact_id or not created_by:
            raise ValueError("mission_id, artifact_id and created_by are required")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT MAX(version) AS version FROM artifacts WHERE mission_id=? AND artifact_id=?",
                (mission_id, artifact_id),
            ).fetchone()
            latest = row["version"] if row is not None else None
            version = 1 if latest is None else int(latest) + 1
            connection.execute(
                "INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?)",
                (mission_id, artifact_id, version, media_type, digest, content, created_by, _now()),
            )
        return {"mission_id": mission_id, "artifact_id": artifact_id, "version": version, "content_hash": digest}

    def latest_artifact(self, mission_id: str, artifact_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE mission_id=? AND artifact_id=? ORDER BY version DESC LIMIT 1",
                (mission_id, artifact_id),
            ).fetchone()
        if row is None:
            raise KeyError((mission_id, artifact_id))
        return dict(row)

    def set_budget(self, mission_id: str, limit_units: int) -> None:
        if limit_units < 0:
            raise ValueError("limit_units must be >= 0")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO budgets VALUES(?,?,0,?)
                ON CONFLICT(mission_id) DO UPDATE SET
                    limit_units=excluded.limit_units,
                    updated_at=excluded.updated_at
                """,
                (mission_id, limit_units, _now()),
            )

    def consume_budget(self, mission_id: str, units: int) -> tuple[int, int]:
        if units <= 0:
            raise ValueError("units must be > 0")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM budgets WHERE mission_id=?", (mission_id,)).fetchone()
            if row is None:
                raise KeyError(mission_id)
            new_total = int(row["consumed_units"]) + units
            limit_units = int(row["limit_units"])
            if new_total > limit_units:
                raise RuntimeError("budget_exhausted")
            connection.execute(
                "UPDATE budgets SET consumed_units=?, updated_at=? WHERE mission_id=?",
                (new_total, _now(), mission_id),
            )
        return new_total, limit_units

    def propose_action(
        self,
        *,
        proposal_id: str,
        mission_id: str,
        action_type: str,
        target: str,
        protected: bool,
    ) -> None:
        with self._connection() as connection:
            try:
                connection.execute(
                    "INSERT INTO approvals VALUES(?,?,?,?,?,'PENDING',NULL,?,NULL)",
                    (proposal_id, mission_id, action_type, target, int(protected), _now()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"duplicate proposal: {proposal_id}") from exc

    def approval_record(self, proposal_id: str, *, mission_id: str | None = None) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM approvals WHERE proposal_id=?", (proposal_id,)).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if mission_id is not None and str(row["mission_id"]) != mission_id:
            raise PermissionError("cross_mission_access_denied")
        return dict(row)

    def decide_action(
        self,
        proposal_id: str,
        *,
        approved: bool,
        decided_by: str,
        mission_id: str | None = None,
    ) -> str:
        status = "APPROVED" if approved else "DENIED"
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT mission_id, status FROM approvals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            if mission_id is not None and str(row["mission_id"]) != mission_id:
                raise PermissionError("cross_mission_access_denied")
            if row["status"] != "PENDING":
                raise RuntimeError("approval_already_decided")
            connection.execute(
                "UPDATE approvals SET status=?, decided_by=?, decided_at=? WHERE proposal_id=?",
                (status, decided_by, _now(), proposal_id),
            )
        return status

    def approval_status(self, proposal_id: str, *, mission_id: str | None = None) -> str:
        return str(self.approval_record(proposal_id, mission_id=mission_id)["status"])
