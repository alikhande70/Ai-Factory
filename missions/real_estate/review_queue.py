from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import sqlite3

from .anomalies import AnomalyFinding, DuplicatePriceDivergenceDetector, FindingSeverity
from .inventory import SQLiteInventoryStore


class ReviewStatus(str, Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ReviewOutcome(str, Enum):
    CONFIRMED_ANOMALY = "CONFIRMED_ANOMALY"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class ReviewCase:
    case_id: str
    finding: AnomalyFinding
    status: ReviewStatus
    assigned_reviewer: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ReviewEvent:
    event_id: int
    case_id: str
    event_type: str
    actor_id: str
    from_status: ReviewStatus | None
    to_status: ReviewStatus
    outcome: ReviewOutcome | None
    evidence_refs: tuple[str, ...]
    note: str
    occurred_at: str
    previous_hash: str
    event_hash: str


class StaleFindingError(RuntimeError):
    pass


class SQLiteTrustReviewStore:
    """Append-audited anomaly queue with no API for mutating inventory trust/state."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str) -> None:
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self.apply_migrations()

    def close(self) -> None:
        self._connection.close()

    def apply_migrations(self) -> int:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS trust_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {int(row[0]) for row in self._connection.execute("SELECT version FROM trust_schema_version").fetchall()}
        if 1 in applied:
            return 0
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE review_cases (
                    case_id TEXT PRIMARY KEY,
                    finding_id TEXT NOT NULL UNIQUE,
                    finding_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    assigned_reviewer TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX idx_review_status ON review_cases(status, updated_at);

                CREATE TABLE review_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL REFERENCES review_cases(case_id),
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    outcome TEXT,
                    evidence_json TEXT NOT NULL,
                    note TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                CREATE INDEX idx_review_event_case ON review_events(case_id, event_id);
                """
            )
            self._connection.execute(
                "INSERT INTO trust_schema_version(version, applied_at) VALUES (?, ?)",
                (1, self._now_iso()),
            )
        return 1

    def queue(self, finding: AnomalyFinding) -> ReviewCase:
        finding.validate()
        existing = self._connection.execute(
            "SELECT case_id FROM review_cases WHERE finding_id = ?", (finding.finding_id,)
        ).fetchone()
        if existing is not None:
            return self.get(str(existing["case_id"]))
        case_id = "CASE-" + hashlib.sha256(finding.finding_id.encode("utf-8")).hexdigest()[:24]
        now = self._now_iso()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO review_cases(case_id, finding_id, finding_json, status, assigned_reviewer, created_at, updated_at)
                VALUES (?, ?, ?, ?, NULL, ?, ?)
                """,
                (case_id, finding.finding_id, self._serialize_finding(finding), ReviewStatus.OPEN.value, now, now),
            )
            self._append_event(
                case_id, "QUEUED", finding.detector_id, None, ReviewStatus.OPEN, None,
                finding.evidence_refs, "Anomaly queued for operator review; no protected domain decision was made.", now,
            )
        return self.get(case_id)

    def get(self, case_id: str) -> ReviewCase:
        row = self._case_row(case_id)
        return ReviewCase(
            case_id=case_id,
            finding=self._deserialize_finding(str(row["finding_json"])),
            status=ReviewStatus(str(row["status"])),
            assigned_reviewer=str(row["assigned_reviewer"]) if row["assigned_reviewer"] is not None else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def open_cases(self) -> tuple[ReviewCase, ...]:
        rows = self._connection.execute(
            "SELECT case_id FROM review_cases WHERE status IN (?, ?) ORDER BY created_at, case_id",
            (ReviewStatus.OPEN.value, ReviewStatus.IN_REVIEW.value),
        ).fetchall()
        return tuple(self.get(str(row["case_id"])) for row in rows)

    def start_review(self, case_id: str, *, reviewer_id: str) -> ReviewCase:
        if not reviewer_id.strip():
            raise ValueError("reviewer_id is required")
        case = self.get(case_id)
        if case.status != ReviewStatus.OPEN:
            raise ValueError(f"review can only start from OPEN, got {case.status.value}")
        if case.finding.severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL} and reviewer_id == case.finding.detector_id:
            raise PermissionError("high-impact anomaly review must be independent from detector")
        now = self._now_iso()
        with self._connection:
            self._connection.execute(
                "UPDATE review_cases SET status = ?, assigned_reviewer = ?, updated_at = ? WHERE case_id = ?",
                (ReviewStatus.IN_REVIEW.value, reviewer_id, now, case_id),
            )
            self._append_event(
                case_id, "REVIEW_STARTED", reviewer_id, ReviewStatus.OPEN, ReviewStatus.IN_REVIEW,
                None, (), "Operator review started.", now,
            )
        return self.get(case_id)

    def resolve(
        self,
        case_id: str,
        *,
        reviewer_id: str,
        outcome: ReviewOutcome,
        evidence_refs: tuple[str, ...],
        note: str,
    ) -> ReviewCase:
        case = self.get(case_id)
        if case.status != ReviewStatus.IN_REVIEW:
            raise ValueError(f"resolution requires IN_REVIEW, got {case.status.value}")
        if reviewer_id != case.assigned_reviewer:
            raise PermissionError("only the assigned reviewer may resolve the case")
        if not evidence_refs:
            raise ValueError("review resolution requires evidence")
        if not note.strip():
            raise ValueError("review resolution requires a note")
        target = ReviewStatus.DISMISSED if outcome == ReviewOutcome.FALSE_POSITIVE else ReviewStatus.RESOLVED
        now = self._now_iso()
        with self._connection:
            self._connection.execute(
                "UPDATE review_cases SET status = ?, updated_at = ? WHERE case_id = ?",
                (target.value, now, case_id),
            )
            self._append_event(
                case_id, "REVIEW_DECIDED", reviewer_id, ReviewStatus.IN_REVIEW, target,
                outcome, evidence_refs, note, now,
            )
        return self.get(case_id)

    def events(self, case_id: str) -> tuple[ReviewEvent, ...]:
        self._case_row(case_id)
        rows = self._connection.execute(
            "SELECT * FROM review_events WHERE case_id = ? ORDER BY event_id", (case_id,)
        ).fetchall()
        return tuple(self._event_from_row(row) for row in rows)

    def verify_audit_chain(self, case_id: str) -> bool:
        previous = "GENESIS"
        for event in self.events(case_id):
            if event.previous_hash != previous:
                return False
            calculated = self._event_hash(
                event.case_id, event.event_type, event.actor_id, event.from_status,
                event.to_status, event.outcome, event.evidence_refs, event.note,
                event.occurred_at, event.previous_hash,
            )
            if calculated != event.event_hash:
                return False
            previous = event.event_hash
        return True

    def _append_event(
        self,
        case_id: str,
        event_type: str,
        actor_id: str,
        from_status: ReviewStatus | None,
        to_status: ReviewStatus,
        outcome: ReviewOutcome | None,
        evidence_refs: tuple[str, ...],
        note: str,
        occurred_at: str,
    ) -> None:
        row = self._connection.execute(
            "SELECT event_hash FROM review_events WHERE case_id = ? ORDER BY event_id DESC LIMIT 1", (case_id,)
        ).fetchone()
        previous = str(row["event_hash"]) if row is not None else "GENESIS"
        event_hash = self._event_hash(
            case_id, event_type, actor_id, from_status, to_status, outcome,
            evidence_refs, note, occurred_at, previous,
        )
        self._connection.execute(
            """
            INSERT INTO review_events(
                case_id, event_type, actor_id, from_status, to_status, outcome,
                evidence_json, note, occurred_at, previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id, event_type, actor_id,
                from_status.value if from_status is not None else None,
                to_status.value, outcome.value if outcome is not None else None,
                json.dumps(evidence_refs), note, occurred_at, previous, event_hash,
            ),
        )

    @staticmethod
    def _event_hash(
        case_id: str,
        event_type: str,
        actor_id: str,
        from_status: ReviewStatus | None,
        to_status: ReviewStatus,
        outcome: ReviewOutcome | None,
        evidence_refs: tuple[str, ...],
        note: str,
        occurred_at: str,
        previous_hash: str,
    ) -> str:
        payload = {
            "case_id": case_id,
            "event_type": event_type,
            "actor_id": actor_id,
            "from_status": from_status.value if from_status is not None else None,
            "to_status": to_status.value,
            "outcome": outcome.value if outcome is not None else None,
            "evidence_refs": list(evidence_refs),
            "note": note,
            "occurred_at": occurred_at,
            "previous_hash": previous_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _case_row(self, case_id: str) -> sqlite3.Row:
        row = self._connection.execute("SELECT * FROM review_cases WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(case_id)
        return row

    @staticmethod
    def _serialize_finding(finding: AnomalyFinding) -> str:
        return json.dumps(
            {
                "finding_id": finding.finding_id,
                "anomaly_type": finding.anomaly_type,
                "severity": finding.severity.value,
                "canonical_id": finding.canonical_id,
                "source_version_ids": list(finding.source_version_ids),
                "detector_id": finding.detector_id,
                "evidence_refs": list(finding.evidence_refs),
                "evidence_fingerprint": finding.evidence_fingerprint,
                "summary": finding.summary,
                "observed_value": finding.observed_value,
                "threshold": finding.threshold,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @staticmethod
    def _deserialize_finding(payload: str) -> AnomalyFinding:
        data = json.loads(payload)
        finding = AnomalyFinding(
            finding_id=str(data["finding_id"]),
            anomaly_type=str(data["anomaly_type"]),
            severity=FindingSeverity(str(data["severity"])),
            canonical_id=str(data["canonical_id"]),
            source_version_ids=tuple(str(value) for value in data["source_version_ids"]),
            detector_id=str(data["detector_id"]),
            evidence_refs=tuple(str(value) for value in data["evidence_refs"]),
            evidence_fingerprint=str(data["evidence_fingerprint"]),
            summary=str(data["summary"]),
            observed_value=float(data["observed_value"]),
            threshold=float(data["threshold"]),
        )
        finding.validate()
        return finding

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> ReviewEvent:
        return ReviewEvent(
            event_id=int(row["event_id"]),
            case_id=str(row["case_id"]),
            event_type=str(row["event_type"]),
            actor_id=str(row["actor_id"]),
            from_status=ReviewStatus(str(row["from_status"])) if row["from_status"] is not None else None,
            to_status=ReviewStatus(str(row["to_status"])),
            outcome=ReviewOutcome(str(row["outcome"])) if row["outcome"] is not None else None,
            evidence_refs=tuple(json.loads(str(row["evidence_json"]))),
            note=str(row["note"]),
            occurred_at=str(row["occurred_at"]),
            previous_hash=str(row["previous_hash"]),
            event_hash=str(row["event_hash"]),
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


class TrustReviewCoordinator:
    """Revalidates detector evidence before a confirmed anomaly resolution."""

    def __init__(
        self,
        inventory: SQLiteInventoryStore,
        review_store: SQLiteTrustReviewStore,
        detector: DuplicatePriceDivergenceDetector,
    ) -> None:
        self._inventory = inventory
        self._review_store = review_store
        self._detector = detector

    def detect_and_queue(self, canonical_id: str) -> ReviewCase | None:
        finding = self._detector.detect(self._inventory, canonical_id)
        return self._review_store.queue(finding) if finding is not None else None

    def resolve_current(
        self,
        case_id: str,
        *,
        reviewer_id: str,
        outcome: ReviewOutcome,
        evidence_refs: tuple[str, ...],
        note: str,
    ) -> ReviewCase:
        case = self._review_store.get(case_id)
        current = self._detector.detect(self._inventory, case.finding.canonical_id)
        if current is None or current.evidence_fingerprint != case.finding.evidence_fingerprint:
            raise StaleFindingError("finding evidence changed; re-detect and re-queue before confirmed resolution")
        return self._review_store.resolve(
            case_id,
            reviewer_id=reviewer_id,
            outcome=outcome,
            evidence_refs=evidence_refs,
            note=note,
        )
