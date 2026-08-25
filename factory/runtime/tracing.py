from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


REDACTED = "***REDACTED***"
SENSITIVE_KEYS = {"auth", "private_value", "access_value", "credential_value"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (REDACTED if str(key).lower() in SENSITIVE_KEYS else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


class SQLiteTracer:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def trace(self, *, mission_id: str, actor_id: str, event_name: str, payload: dict[str, Any]) -> int:
        if not mission_id or not actor_id or not event_name:
            raise ValueError("mission_id, actor_id and event_name are required")
        safe = _redact(payload)
        encoded = json.dumps(safe, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                "INSERT INTO traces(mission_id,actor_id,event_name,payload_json,created_at) VALUES(?,?,?,?,?)",
                (mission_id, actor_id, event_name, encoded, _now()),
            )
            return int(cursor.lastrowid)

    def events(self, mission_id: str) -> tuple[dict[str, Any], ...]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM traces WHERE mission_id=? ORDER BY sequence", (mission_id,)
            ).fetchall()
        return tuple(
            {
                "sequence": int(row["sequence"]),
                "mission_id": str(row["mission_id"]),
                "actor_id": str(row["actor_id"]),
                "event_name": str(row["event_name"]),
                "payload": json.loads(str(row["payload_json"])),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        )
