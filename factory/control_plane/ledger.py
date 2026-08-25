from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    event_id: str
    mission_id: str
    actor_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: str
    previous_hash: str
    event_hash: str

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "mission_id": self.mission_id,
            "actor_id": self.actor_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": self.created_at,
            "previous_hash": self.previous_hash,
        }


@dataclass
class AuditLedger:
    """In-memory append-only hash-chained ledger for the Phase 1 control plane.

    Persistence is deliberately deferred to Phase 2. The hash chain makes mutation
    detectable and gives replay code a deterministic ordering primitive now.
    """

    _events: list[AuditEvent] = field(default_factory=list)

    def append(
        self,
        *,
        event_id: str,
        mission_id: str,
        actor_id: str,
        event_type: str,
        payload: dict[str, Any],
        created_at: str | None = None,
    ) -> AuditEvent:
        if any(event.event_id == event_id for event in self._events):
            raise ValueError(f"duplicate event id: {event_id}")
        if not mission_id or not actor_id or not event_type:
            raise ValueError("mission_id, actor_id and event_type are required")

        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        sequence = len(self._events) + 1
        previous_hash = self._events[-1].event_hash if self._events else "GENESIS"
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
        event_hash = hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()
        event = AuditEvent(event_hash=event_hash, **unsigned)
        self._events.append(event)
        return event

    def events(self, mission_id: str | None = None) -> tuple[AuditEvent, ...]:
        if mission_id is None:
            return tuple(self._events)
        return tuple(event for event in self._events if event.mission_id == mission_id)

    def verify_integrity(self) -> None:
        previous_hash = "GENESIS"
        for expected_sequence, event in enumerate(self._events, start=1):
            if event.sequence != expected_sequence:
                raise ValueError("audit sequence gap or reordering detected")
            if event.previous_hash != previous_hash:
                raise ValueError("audit hash-chain break detected")
            calculated = hashlib.sha256(
                _canonical_json(event.unsigned_payload()).encode("utf-8")
            ).hexdigest()
            if calculated != event.event_hash:
                raise ValueError("audit event mutation detected")
            previous_hash = event.event_hash

    @classmethod
    def from_events(cls, events: Iterable[AuditEvent]) -> "AuditLedger":
        ledger = cls(list(events))
        ledger.verify_integrity()
        return ledger
