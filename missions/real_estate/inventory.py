from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Iterable

from .contracts import ListingCandidate, ListingState, RightsBasis
from .integrity import FreshnessPolicy, duplicate_fingerprint, ensure_ingestion_allowed, freshness_score, transition_listing_state


@dataclass(frozen=True)
class PublisherTrustEvidence:
    publisher_id: str
    score: float
    evidence_refs: tuple[str, ...]
    verified_by: str

    def validate(self) -> None:
        if not self.publisher_id.strip():
            raise ValueError("publisher_id is required")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("trust score must be between 0 and 1")
        if not self.evidence_refs:
            raise ValueError("publisher trust requires evidence")
        if not self.verified_by.strip():
            raise ValueError("verified_by is required")


@dataclass(frozen=True)
class InventoryQuery:
    transaction_type: str | None = None
    property_type: str | None = None
    city: str | None = None
    locality: str | None = None
    min_price_minor: int | None = None
    max_price_minor: int | None = None
    bedrooms: int | None = None
    states: tuple[ListingState, ...] = (ListingState.ACTIVE, ListingState.UNDER_OFFER)

    def validate(self) -> None:
        if self.min_price_minor is not None and self.min_price_minor < 0:
            raise ValueError("min_price_minor must be non-negative")
        if self.max_price_minor is not None and self.max_price_minor < 0:
            raise ValueError("max_price_minor must be non-negative")
        if (
            self.min_price_minor is not None
            and self.max_price_minor is not None
            and self.min_price_minor > self.max_price_minor
        ):
            raise ValueError("min_price_minor cannot exceed max_price_minor")


class SQLiteInventoryStore:
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
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {
            int(row[0])
            for row in self._connection.execute("SELECT version FROM schema_version").fetchall()
        }
        count = 0
        if 1 not in applied:
            with self._connection:
                self._connection.executescript(
                    """
                    CREATE TABLE source_records (
                        source_version_id TEXT PRIMARY KEY,
                        listing_id TEXT NOT NULL,
                        source_ref TEXT NOT NULL,
                        publisher_id TEXT NOT NULL,
                        rights_basis TEXT NOT NULL,
                        transaction_type TEXT NOT NULL,
                        property_type TEXT NOT NULL,
                        city TEXT NOT NULL,
                        locality TEXT NOT NULL,
                        geo_cell TEXT NOT NULL,
                        price_minor INTEGER NOT NULL,
                        area_sqm REAL NOT NULL,
                        bedrooms INTEGER,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        image_hashes_json TEXT NOT NULL,
                        source_updated_at TEXT NOT NULL,
                        last_verified_at TEXT NOT NULL,
                        submitted_state TEXT NOT NULL,
                        duplicate_fingerprint TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX idx_source_fingerprint ON source_records(duplicate_fingerprint);
                    CREATE TABLE canonical_listings (
                        canonical_id TEXT PRIMARY KEY,
                        duplicate_fingerprint TEXT NOT NULL UNIQUE,
                        active_source_version_id TEXT NOT NULL REFERENCES source_records(source_version_id),
                        state TEXT NOT NULL,
                        transaction_type TEXT NOT NULL,
                        property_type TEXT NOT NULL,
                        city TEXT NOT NULL,
                        locality TEXT NOT NULL,
                        geo_cell TEXT NOT NULL,
                        price_minor INTEGER NOT NULL,
                        area_sqm REAL NOT NULL,
                        bedrooms INTEGER,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        last_verified_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE duplicate_membership (
                        canonical_id TEXT NOT NULL REFERENCES canonical_listings(canonical_id),
                        source_version_id TEXT NOT NULL UNIQUE REFERENCES source_records(source_version_id),
                        joined_at TEXT NOT NULL,
                        PRIMARY KEY(canonical_id, source_version_id)
                    );
                    CREATE TABLE lifecycle_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        canonical_id TEXT NOT NULL REFERENCES canonical_listings(canonical_id),
                        from_state TEXT,
                        to_state TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        occurred_at TEXT NOT NULL
                    );
                    CREATE TABLE publisher_trust (
                        publisher_id TEXT PRIMARY KEY,
                        score REAL NOT NULL,
                        evidence_json TEXT NOT NULL,
                        verified_by TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )
                self._connection.execute(
                    "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
                    (1, self._now_iso()),
                )
            count += 1
        return count

    def add_source(self, candidate: ListingCandidate, *, actor_id: str = "INGESTION") -> str:
        ensure_ingestion_allowed(candidate)
        fingerprint = duplicate_fingerprint(candidate)
        source_version_id = self._source_version_id(candidate)
        canonical_id = f"CAN-{fingerprint[:20]}"
        now = self._now_iso()

        with self._connection:
            existing = self._connection.execute(
                "SELECT source_version_id FROM source_records WHERE source_version_id = ?",
                (source_version_id,),
            ).fetchone()
            if existing is not None:
                return canonical_id

            self._connection.execute(
                """
                INSERT INTO source_records(
                    source_version_id, listing_id, source_ref, publisher_id, rights_basis,
                    transaction_type, property_type, city, locality, geo_cell, price_minor,
                    area_sqm, bedrooms, title, description, image_hashes_json,
                    source_updated_at, last_verified_at, submitted_state,
                    duplicate_fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_version_id,
                    candidate.listing_id,
                    candidate.source_ref,
                    candidate.publisher_id,
                    candidate.rights_basis.value,
                    candidate.transaction_type,
                    candidate.property_type,
                    candidate.city,
                    candidate.locality,
                    candidate.geo_cell,
                    candidate.price_minor,
                    candidate.area_sqm,
                    candidate.bedrooms,
                    candidate.title,
                    candidate.description,
                    json.dumps(candidate.image_hashes),
                    candidate.source_updated_at.isoformat(),
                    candidate.last_verified_at.isoformat(),
                    candidate.state.value,
                    fingerprint,
                    now,
                ),
            )

            canonical = self._connection.execute(
                "SELECT * FROM canonical_listings WHERE duplicate_fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if canonical is None:
                initial_state = candidate.state
                self._connection.execute(
                    """
                    INSERT INTO canonical_listings(
                        canonical_id, duplicate_fingerprint, active_source_version_id, state,
                        transaction_type, property_type, city, locality, geo_cell, price_minor,
                        area_sqm, bedrooms, title, description, last_verified_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_id,
                        fingerprint,
                        source_version_id,
                        initial_state.value,
                        candidate.transaction_type,
                        candidate.property_type,
                        candidate.city,
                        candidate.locality,
                        candidate.geo_cell,
                        candidate.price_minor,
                        candidate.area_sqm,
                        candidate.bedrooms,
                        candidate.title,
                        candidate.description,
                        candidate.last_verified_at.isoformat(),
                        now,
                    ),
                )
                self._append_event(
                    canonical_id,
                    None,
                    initial_state,
                    reason="CANONICAL_CREATED",
                    actor_id=actor_id,
                    occurred_at=now,
                )
            else:
                canonical_id = str(canonical["canonical_id"])
                current_verified = datetime.fromisoformat(str(canonical["last_verified_at"]))
                if candidate.last_verified_at > current_verified:
                    self._connection.execute(
                        """
                        UPDATE canonical_listings SET
                            active_source_version_id = ?, transaction_type = ?, property_type = ?,
                            city = ?, locality = ?, geo_cell = ?, price_minor = ?, area_sqm = ?,
                            bedrooms = ?, title = ?, description = ?, last_verified_at = ?, updated_at = ?
                        WHERE canonical_id = ?
                        """,
                        (
                            source_version_id,
                            candidate.transaction_type,
                            candidate.property_type,
                            candidate.city,
                            candidate.locality,
                            candidate.geo_cell,
                            candidate.price_minor,
                            candidate.area_sqm,
                            candidate.bedrooms,
                            candidate.title,
                            candidate.description,
                            candidate.last_verified_at.isoformat(),
                            now,
                            canonical_id,
                        ),
                    )

            self._connection.execute(
                "INSERT INTO duplicate_membership(canonical_id, source_version_id, joined_at) VALUES (?, ?, ?)",
                (canonical_id, source_version_id, now),
            )
        return canonical_id

    def transition(
        self,
        canonical_id: str,
        target: ListingState,
        *,
        reason: str,
        actor_id: str,
    ) -> None:
        row = self._canonical_row(canonical_id)
        current = ListingState(str(row["state"]))
        resolved = transition_listing_state(current, target)
        if resolved == current:
            return
        now = self._now_iso()
        with self._connection:
            self._connection.execute(
                "UPDATE canonical_listings SET state = ?, updated_at = ? WHERE canonical_id = ?",
                (resolved.value, now, canonical_id),
            )
            self._append_event(canonical_id, current, resolved, reason=reason, actor_id=actor_id, occurred_at=now)

    def expire_stale(
        self,
        *,
        policy: FreshnessPolicy,
        now: datetime,
        actor_id: str = "FRESHNESS-SWEEPER",
    ) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT * FROM canonical_listings WHERE state IN (?, ?)",
            (ListingState.ACTIVE.value, ListingState.UNDER_OFFER.value),
        ).fetchall()
        expired: list[str] = []
        for row in rows:
            source = self.source_record(str(row["active_source_version_id"]))
            candidate = self._candidate_from_source(source, state=ListingState(str(row["state"])))
            if freshness_score(candidate, policy=policy, now=now) == 0.0:
                canonical_id = str(row["canonical_id"])
                self.transition(canonical_id, ListingState.EXPIRED, reason="FRESHNESS_EXPIRED", actor_id=actor_id)
                expired.append(canonical_id)
        return tuple(expired)

    def record_publisher_trust(self, evidence: PublisherTrustEvidence) -> None:
        evidence.validate()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO publisher_trust(publisher_id, score, evidence_json, verified_by, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(publisher_id) DO UPDATE SET
                    score = excluded.score,
                    evidence_json = excluded.evidence_json,
                    verified_by = excluded.verified_by,
                    updated_at = excluded.updated_at
                """,
                (
                    evidence.publisher_id,
                    evidence.score,
                    json.dumps(evidence.evidence_refs),
                    evidence.verified_by,
                    self._now_iso(),
                ),
            )

    def publisher_trust(self, publisher_id: str) -> PublisherTrustEvidence | None:
        row = self._connection.execute(
            "SELECT * FROM publisher_trust WHERE publisher_id = ?",
            (publisher_id,),
        ).fetchone()
        if row is None:
            return None
        return PublisherTrustEvidence(
            publisher_id=str(row["publisher_id"]),
            score=float(row["score"]),
            evidence_refs=tuple(json.loads(str(row["evidence_json"]))),
            verified_by=str(row["verified_by"]),
        )

    def query(self, query: InventoryQuery) -> tuple[dict[str, object], ...]:
        query.validate()
        clauses: list[str] = []
        params: list[object] = []
        if query.states:
            placeholders = ",".join("?" for _ in query.states)
            clauses.append(f"state IN ({placeholders})")
            params.extend(state.value for state in query.states)
        for column, value in (
            ("transaction_type", query.transaction_type),
            ("property_type", query.property_type),
            ("city", query.city),
            ("locality", query.locality),
            ("bedrooms", query.bedrooms),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if query.min_price_minor is not None:
            clauses.append("price_minor >= ?")
            params.append(query.min_price_minor)
        if query.max_price_minor is not None:
            clauses.append("price_minor <= ?")
            params.append(query.max_price_minor)
        sql = "SELECT * FROM canonical_listings"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY last_verified_at DESC, canonical_id ASC"
        return tuple(dict(row) for row in self._connection.execute(sql, params).fetchall())

    def canonical(self, canonical_id: str) -> dict[str, object]:
        return dict(self._canonical_row(canonical_id))

    def source_record(self, source_version_id: str) -> dict[str, object]:
        row = self._connection.execute(
            "SELECT * FROM source_records WHERE source_version_id = ?",
            (source_version_id,),
        ).fetchone()
        if row is None:
            raise KeyError(source_version_id)
        return dict(row)

    def source_members(self, canonical_id: str) -> tuple[dict[str, object], ...]:
        rows = self._connection.execute(
            """
            SELECT s.* FROM source_records s
            JOIN duplicate_membership d ON d.source_version_id = s.source_version_id
            WHERE d.canonical_id = ? ORDER BY s.created_at, s.source_version_id
            """,
            (canonical_id,),
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def lifecycle(self, canonical_id: str) -> tuple[dict[str, object], ...]:
        rows = self._connection.execute(
            "SELECT * FROM lifecycle_events WHERE canonical_id = ? ORDER BY event_id",
            (canonical_id,),
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def counts(self) -> dict[str, int]:
        return {
            "source_records": int(self._connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0]),
            "canonical_listings": int(self._connection.execute("SELECT COUNT(*) FROM canonical_listings").fetchone()[0]),
            "memberships": int(self._connection.execute("SELECT COUNT(*) FROM duplicate_membership").fetchone()[0]),
            "lifecycle_events": int(self._connection.execute("SELECT COUNT(*) FROM lifecycle_events").fetchone()[0]),
        }

    def _canonical_row(self, canonical_id: str) -> sqlite3.Row:
        row = self._connection.execute(
            "SELECT * FROM canonical_listings WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchone()
        if row is None:
            raise KeyError(canonical_id)
        return row

    def _append_event(
        self,
        canonical_id: str,
        from_state: ListingState | None,
        to_state: ListingState,
        *,
        reason: str,
        actor_id: str,
        occurred_at: str,
    ) -> None:
        if not reason.strip() or not actor_id.strip():
            raise ValueError("lifecycle reason and actor_id are required")
        self._connection.execute(
            """
            INSERT INTO lifecycle_events(canonical_id, from_state, to_state, reason, actor_id, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                canonical_id,
                from_state.value if from_state is not None else None,
                to_state.value,
                reason,
                actor_id,
                occurred_at,
            ),
        )

    @staticmethod
    def _source_version_id(candidate: ListingCandidate) -> str:
        payload = "|".join(
            (
                candidate.source_ref,
                candidate.publisher_id,
                candidate.source_updated_at.isoformat(),
                candidate.last_verified_at.isoformat(),
                candidate.state.value,
                str(candidate.price_minor),
                str(candidate.area_sqm),
                str(candidate.bedrooms),
                candidate.title,
                candidate.description,
                ",".join(candidate.image_hashes),
            )
        )
        return "SRC-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _candidate_from_source(source: dict[str, object], *, state: ListingState) -> ListingCandidate:
        return ListingCandidate(
            listing_id=str(source["listing_id"]),
            source_ref=str(source["source_ref"]),
            publisher_id=str(source["publisher_id"]),
            rights_basis=RightsBasis(str(source["rights_basis"])),
            transaction_type=str(source["transaction_type"]),
            property_type=str(source["property_type"]),
            city=str(source["city"]),
            locality=str(source["locality"]),
            geo_cell=str(source["geo_cell"]),
            price_minor=int(source["price_minor"]),
            area_sqm=float(source["area_sqm"]),
            bedrooms=int(source["bedrooms"]) if source["bedrooms"] is not None else None,
            title=str(source["title"]),
            description=str(source["description"]),
            image_hashes=tuple(json.loads(str(source["image_hashes_json"]))),
            source_updated_at=datetime.fromisoformat(str(source["source_updated_at"])),
            last_verified_at=datetime.fromisoformat(str(source["last_verified_at"])),
            state=state,
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
