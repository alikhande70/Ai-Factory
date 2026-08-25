from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from .catalog import SQLiteRuntimeCatalog


INCIDENT_STATUSES = (
    "DECLARED",
    "TRIAGED",
    "CONTAINING",
    "CONTAINED",
    "RECOVERING",
    "MONITORING",
    "CLOSED",
)
INCIDENT_SEVERITIES = ("SEV1", "SEV2", "SEV3", "SEV4")
ALLOWED_TRANSITIONS = {
    "DECLARED": {"TRIAGED"},
    "TRIAGED": {"CONTAINING"},
    "CONTAINING": {"CONTAINED"},
    "CONTAINED": {"RECOVERING"},
    "RECOVERING": {"MONITORING"},
    "MONITORING": {"CLOSED", "RECOVERING"},
    "CLOSED": set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class IncidentRecord:
    incident_id: str
    mission_id: str
    severity: str
    title: str
    status: str
    declared_by: str
    affected_scope: tuple[str, ...]
    recovery_verified: bool
    created_at: str
    updated_at: str


class IncidentResponseStore:
    """Durable deterministic incident-response state and evidence boundary.

    Every incident mutation is paired atomically with a per-incident hash-chained event.
    There is intentionally no delete API for incidents, evidence or history.
    """

    def __init__(self, path: str | Path, *, runtime_catalog: SQLiteRuntimeCatalog | None = None) -> None:
        self.path = str(path)
        self.runtime_catalog = runtime_catalog
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
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    severity TEXT NOT NULL CHECK(severity IN ('SEV1','SEV2','SEV3','SEV4')),
                    title TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('DECLARED','TRIAGED','CONTAINING','CONTAINED','RECOVERING','MONITORING','CLOSED')),
                    declared_by TEXT NOT NULL,
                    affected_scope_json TEXT NOT NULL,
                    recovery_verified INTEGER NOT NULL DEFAULT 0 CHECK(recovery_verified IN (0,1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS incident_evidence (
                    incident_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    reference TEXT NOT NULL,
                    recorded_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(incident_id,evidence_id),
                    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id)
                );
                CREATE TABLE IF NOT EXISTS incident_actions (
                    incident_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    protected INTEGER NOT NULL CHECK(protected IN (0,1)),
                    proposal_id TEXT,
                    status TEXT NOT NULL CHECK(status IN ('PLANNED','EXECUTED','FAILED')),
                    actor_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    executed_at TEXT,
                    PRIMARY KEY(incident_id,action_id),
                    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id)
                );
                CREATE TABLE IF NOT EXISTS incident_events (
                    incident_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    PRIMARY KEY(incident_id,sequence),
                    UNIQUE(incident_id,event_hash),
                    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id)
                );
                """
            )

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        incident_id: str,
        event_type: str,
        actor_id: str,
        payload: dict[str, Any],
        created_at: str,
    ) -> str:
        last = connection.execute(
            "SELECT sequence,event_hash FROM incident_events WHERE incident_id=? ORDER BY sequence DESC LIMIT 1",
            (incident_id,),
        ).fetchone()
        sequence = 1 if last is None else int(last["sequence"]) + 1
        previous_hash = "GENESIS" if last is None else str(last["event_hash"])
        unsigned = {
            "incident_id": incident_id,
            "sequence": sequence,
            "event_type": event_type,
            "actor_id": actor_id,
            "payload": payload,
            "created_at": created_at,
            "previous_hash": previous_hash,
        }
        event_hash = hashlib.sha256(_canonical(unsigned).encode("utf-8")).hexdigest()
        connection.execute(
            "INSERT INTO incident_events VALUES(?,?,?,?,?,?,?,?)",
            (
                incident_id,
                sequence,
                event_type,
                actor_id,
                _canonical(payload),
                created_at,
                previous_hash,
                event_hash,
            ),
        )
        return event_hash

    def declare(
        self,
        *,
        incident_id: str,
        mission_id: str,
        severity: str,
        title: str,
        declared_by: str,
        affected_scope: tuple[str, ...],
    ) -> IncidentRecord:
        if severity not in INCIDENT_SEVERITIES:
            raise ValueError("invalid incident severity")
        if not all(value.strip() for value in (incident_id, mission_id, title, declared_by)):
            raise ValueError("incident identity, mission, title and declarer are required")
        if not affected_scope or any(not item.strip() for item in affected_scope):
            raise ValueError("affected_scope must contain explicit resources")
        timestamp = _now()
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO incidents VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        incident_id,
                        mission_id,
                        severity,
                        title,
                        "DECLARED",
                        declared_by,
                        _canonical(list(affected_scope)),
                        0,
                        timestamp,
                        timestamp,
                    ),
                )
                self._append_event(
                    connection,
                    incident_id=incident_id,
                    event_type="INCIDENT_DECLARED",
                    actor_id=declared_by,
                    payload={"severity": severity, "affected_scope": list(affected_scope)},
                    created_at=timestamp,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("duplicate incident id") from exc
        return self.get(incident_id, mission_id=mission_id)

    def get(self, incident_id: str, *, mission_id: str | None = None) -> IncidentRecord:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
        if row is None:
            raise KeyError(incident_id)
        if mission_id is not None and str(row["mission_id"]) != mission_id:
            raise PermissionError("cross_mission_incident_access_denied")
        return IncidentRecord(
            incident_id=str(row["incident_id"]),
            mission_id=str(row["mission_id"]),
            severity=str(row["severity"]),
            title=str(row["title"]),
            status=str(row["status"]),
            declared_by=str(row["declared_by"]),
            affected_scope=tuple(json.loads(str(row["affected_scope_json"]))),
            recovery_verified=bool(row["recovery_verified"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def transition(self, incident_id: str, *, mission_id: str, actor_id: str, new_status: str) -> IncidentRecord:
        if new_status not in INCIDENT_STATUSES:
            raise ValueError("invalid incident status")
        timestamp = _now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT mission_id,status,recovery_verified FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
            if row is None:
                raise KeyError(incident_id)
            if str(row["mission_id"]) != mission_id:
                raise PermissionError("cross_mission_incident_access_denied")
            current = str(row["status"])
            if new_status not in ALLOWED_TRANSITIONS[current]:
                raise RuntimeError(f"illegal_incident_transition:{current}->{new_status}")
            if new_status == "CLOSED":
                if not bool(row["recovery_verified"]):
                    raise RuntimeError("incident_recovery_not_verified")
                evidence = connection.execute("SELECT COUNT(*) AS n FROM incident_evidence WHERE incident_id=?", (incident_id,)).fetchone()
                if int(evidence["n"]) < 1:
                    raise RuntimeError("incident_closure_requires_evidence")
            connection.execute(
                "UPDATE incidents SET status=?,updated_at=? WHERE incident_id=?",
                (new_status, timestamp, incident_id),
            )
            self._append_event(
                connection,
                incident_id=incident_id,
                event_type="STATUS_CHANGED",
                actor_id=actor_id,
                payload={"from": current, "to": new_status},
                created_at=timestamp,
            )
        return self.get(incident_id, mission_id=mission_id)

    def record_evidence(
        self,
        incident_id: str,
        *,
        mission_id: str,
        evidence_id: str,
        kind: str,
        reference: str,
        recorded_by: str,
    ) -> None:
        timestamp = _now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT mission_id FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
            if row is None:
                raise KeyError(incident_id)
            if str(row["mission_id"]) != mission_id:
                raise PermissionError("cross_mission_incident_access_denied")
            connection.execute(
                "INSERT INTO incident_evidence VALUES(?,?,?,?,?,?)",
                (incident_id, evidence_id, kind, reference, recorded_by, timestamp),
            )
            self._append_event(
                connection,
                incident_id=incident_id,
                event_type="EVIDENCE_RECORDED",
                actor_id=recorded_by,
                payload={"evidence_id": evidence_id, "kind": kind, "reference": reference},
                created_at=timestamp,
            )

    def plan_action(
        self,
        incident_id: str,
        *,
        mission_id: str,
        action_id: str,
        action_type: str,
        target: str,
        protected: bool,
        actor_id: str,
        proposal_id: str | None = None,
    ) -> None:
        if protected and not proposal_id:
            raise ValueError("protected incident action requires approval proposal_id")
        timestamp = _now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT mission_id FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
            if row is None:
                raise KeyError(incident_id)
            if str(row["mission_id"]) != mission_id:
                raise PermissionError("cross_mission_incident_access_denied")
            connection.execute(
                "INSERT INTO incident_actions VALUES(?,?,?,?,?,?,'PLANNED',?,?,NULL)",
                (incident_id, action_id, action_type, target, int(protected), proposal_id, actor_id, timestamp),
            )
            self._append_event(
                connection,
                incident_id=incident_id,
                event_type="ACTION_PLANNED",
                actor_id=actor_id,
                payload={"action_id": action_id, "action_type": action_type, "target": target, "protected": protected, "proposal_id": proposal_id},
                created_at=timestamp,
            )

    def mark_action_executed(self, incident_id: str, *, mission_id: str, action_id: str, actor_id: str) -> None:
        timestamp = _now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            incident = connection.execute("SELECT mission_id FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
            if incident is None:
                raise KeyError(incident_id)
            if str(incident["mission_id"]) != mission_id:
                raise PermissionError("cross_mission_incident_access_denied")
            action = connection.execute(
                "SELECT protected,proposal_id,status FROM incident_actions WHERE incident_id=? AND action_id=?",
                (incident_id, action_id),
            ).fetchone()
            if action is None:
                raise KeyError(action_id)
            if str(action["status"]) != "PLANNED":
                raise RuntimeError("incident_action_already_decided")
            if bool(action["protected"]):
                if self.runtime_catalog is None:
                    raise RuntimeError("approval_catalog_required")
                proposal_id = str(action["proposal_id"])
                if self.runtime_catalog.approval_status(proposal_id, mission_id=mission_id) != "APPROVED":
                    raise PermissionError("human_approval_required")
            connection.execute(
                "UPDATE incident_actions SET status='EXECUTED',executed_at=? WHERE incident_id=? AND action_id=?",
                (timestamp, incident_id, action_id),
            )
            self._append_event(
                connection,
                incident_id=incident_id,
                event_type="ACTION_EXECUTED",
                actor_id=actor_id,
                payload={"action_id": action_id},
                created_at=timestamp,
            )

    def verify_recovery(self, incident_id: str, *, mission_id: str, actor_id: str, evidence_id: str) -> None:
        timestamp = _now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            incident = connection.execute("SELECT mission_id,status FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
            if incident is None:
                raise KeyError(incident_id)
            if str(incident["mission_id"]) != mission_id:
                raise PermissionError("cross_mission_incident_access_denied")
            if str(incident["status"]) not in {"RECOVERING", "MONITORING"}:
                raise RuntimeError("recovery_verification_not_allowed_in_current_state")
            evidence = connection.execute(
                "SELECT 1 FROM incident_evidence WHERE incident_id=? AND evidence_id=?",
                (incident_id, evidence_id),
            ).fetchone()
            if evidence is None:
                raise RuntimeError("recovery_verification_requires_recorded_evidence")
            connection.execute(
                "UPDATE incidents SET recovery_verified=1,updated_at=? WHERE incident_id=?",
                (timestamp, incident_id),
            )
            self._append_event(
                connection,
                incident_id=incident_id,
                event_type="RECOVERY_VERIFIED",
                actor_id=actor_id,
                payload={"evidence_id": evidence_id},
                created_at=timestamp,
            )

    def verify_history(self, incident_id: str, *, mission_id: str) -> None:
        self.get(incident_id, mission_id=mission_id)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM incident_events WHERE incident_id=? ORDER BY sequence",
                (incident_id,),
            ).fetchall()
        previous_hash = "GENESIS"
        for expected_sequence, row in enumerate(rows, start=1):
            if int(row["sequence"]) != expected_sequence:
                raise ValueError("incident event sequence gap")
            if str(row["previous_hash"]) != previous_hash:
                raise ValueError("incident event chain break")
            unsigned = {
                "incident_id": incident_id,
                "sequence": expected_sequence,
                "event_type": str(row["event_type"]),
                "actor_id": str(row["actor_id"]),
                "payload": json.loads(str(row["payload_json"])),
                "created_at": str(row["created_at"]),
                "previous_hash": previous_hash,
            }
            calculated = hashlib.sha256(_canonical(unsigned).encode("utf-8")).hexdigest()
            if calculated != str(row["event_hash"]):
                raise ValueError("incident event mutation detected")
            previous_hash = str(row["event_hash"])
