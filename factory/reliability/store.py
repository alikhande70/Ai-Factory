from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from .contracts import AttemptRecord, OperationSpec, RecoveryDecision


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class SQLiteReliabilityStore:
    """Durable operation journal. Decisions are persisted before a caller acts on them."""

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
                CREATE TABLE IF NOT EXISTS reliability_operations (
                    operation_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    spec_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'READY','RETRY_READY','RECONCILE_REQUIRED','COMPLETED','STOPPED'
                    )),
                    latest_attempt INTEGER NOT NULL DEFAULT 0 CHECK(latest_attempt >= 0),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reliability_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL,
                    event_type TEXT NOT NULL CHECK(event_type IN ('ATTEMPT','RECONCILIATION','DECISION')),
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(operation_id) REFERENCES reliability_operations(operation_id)
                );
                CREATE INDEX IF NOT EXISTS idx_reliability_events_operation
                    ON reliability_events(operation_id, sequence);
                """
            )

    def register(self, operation: OperationSpec) -> None:
        operation.validate()
        with self._connection() as connection:
            try:
                connection.execute(
                    "INSERT INTO reliability_operations VALUES(?,?,?,?,?,?)",
                    (
                        operation.operation_id,
                        operation.mission_id,
                        _json(asdict(operation)),
                        "READY",
                        0,
                        _now(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"duplicate reliability operation:{operation.operation_id}") from exc

    def load_operation(self, operation_id: str) -> OperationSpec:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT spec_json FROM reliability_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
        if row is None:
            raise KeyError(operation_id)
        operation = OperationSpec(**json.loads(str(row["spec_json"])))
        operation.validate()
        return operation

    def state(self, operation_id: str) -> dict[str, object]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT operation_id, mission_id, status, latest_attempt, updated_at "
                "FROM reliability_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
        if row is None:
            raise KeyError(operation_id)
        return dict(row)

    def append_attempt_and_decision(
        self,
        *,
        attempt: AttemptRecord,
        decision: RecoveryDecision,
    ) -> None:
        attempt.validate()
        decision.validate()
        if attempt.operation_id != decision.operation_id:
            raise ValueError("attempt/decision operation mismatch")
        status = self._status_for(decision)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT latest_attempt, status FROM reliability_operations WHERE operation_id=?",
                (attempt.operation_id,),
            ).fetchone()
            if row is None:
                raise KeyError(attempt.operation_id)
            if row["status"] in {"COMPLETED", "STOPPED"}:
                raise RuntimeError("terminal reliability operation cannot accept attempts")
            expected = int(row["latest_attempt"]) + 1
            if attempt.attempt != expected:
                raise ValueError(f"attempt sequence mismatch:expected={expected}:actual={attempt.attempt}")
            connection.execute(
                "INSERT INTO reliability_events(operation_id,event_type,payload_json,created_at) VALUES(?,?,?,?)",
                (attempt.operation_id, "ATTEMPT", _json(asdict(attempt)), _now()),
            )
            connection.execute(
                "INSERT INTO reliability_events(operation_id,event_type,payload_json,created_at) VALUES(?,?,?,?)",
                (decision.operation_id, "DECISION", _json(asdict(decision)), _now()),
            )
            connection.execute(
                "UPDATE reliability_operations SET status=?, latest_attempt=?, updated_at=? WHERE operation_id=?",
                (status, attempt.attempt, _now(), attempt.operation_id),
            )

    def append_reconciliation_and_decision(
        self,
        *,
        operation_id: str,
        reconciliation_result: str,
        decision: RecoveryDecision,
    ) -> None:
        decision.validate()
        if decision.operation_id != operation_id:
            raise ValueError("reconciliation/decision operation mismatch")
        if reconciliation_result not in {"APPLIED", "NOT_APPLIED", "UNKNOWN"}:
            raise ValueError("invalid reconciliation_result")
        status = self._status_for(decision)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM reliability_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise KeyError(operation_id)
            if row["status"] != "RECONCILE_REQUIRED":
                raise RuntimeError("reconciliation not currently required")
            connection.execute(
                "INSERT INTO reliability_events(operation_id,event_type,payload_json,created_at) VALUES(?,?,?,?)",
                (operation_id, "RECONCILIATION", _json({"result": reconciliation_result}), _now()),
            )
            connection.execute(
                "INSERT INTO reliability_events(operation_id,event_type,payload_json,created_at) VALUES(?,?,?,?)",
                (operation_id, "DECISION", _json(asdict(decision)), _now()),
            )
            connection.execute(
                "UPDATE reliability_operations SET status=?, updated_at=? WHERE operation_id=?",
                (status, _now(), operation_id),
            )

    def latest_attempt(self, operation_id: str) -> AttemptRecord:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM reliability_events "
                "WHERE operation_id=? AND event_type='ATTEMPT' ORDER BY sequence DESC LIMIT 1",
                (operation_id,),
            ).fetchone()
        if row is None:
            raise KeyError((operation_id, "attempt"))
        attempt = AttemptRecord(**json.loads(str(row["payload_json"])))
        attempt.validate()
        return attempt

    def latest_decision(self, operation_id: str) -> RecoveryDecision:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM reliability_events "
                "WHERE operation_id=? AND event_type='DECISION' ORDER BY sequence DESC LIMIT 1",
                (operation_id,),
            ).fetchone()
        if row is None:
            raise KeyError((operation_id, "decision"))
        decision = RecoveryDecision(**json.loads(str(row["payload_json"])))
        decision.validate()
        return decision

    def events(self, operation_id: str) -> tuple[dict[str, object], ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT sequence,event_type,payload_json,created_at FROM reliability_events "
                "WHERE operation_id=? ORDER BY sequence",
                (operation_id,),
            ).fetchall()
        return tuple(
            {
                "sequence": int(row["sequence"]),
                "event_type": str(row["event_type"]),
                "payload": json.loads(str(row["payload_json"])),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        )

    @staticmethod
    def _status_for(decision: RecoveryDecision) -> str:
        return {
            "COMPLETE": "COMPLETED",
            "RETRY": "RETRY_READY",
            "RECONCILE": "RECONCILE_REQUIRED",
            "STOP": "STOPPED",
        }[decision.action]
