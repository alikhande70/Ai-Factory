from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import sqlite3

from .contracts import ListingState
from .search import RealEstateSearchService, SearchQuery


@dataclass(frozen=True)
class SavedSearch:
    saved_search_id: str
    owner_id: str
    name: str
    query: SearchQuery
    enabled: bool = True
    version: int = 1

    def validate(self) -> None:
        if not self.saved_search_id.strip():
            raise ValueError("saved_search_id is required")
        if not self.owner_id.strip():
            raise ValueError("owner_id is required")
        if not self.name.strip():
            raise ValueError("name is required")
        if self.version <= 0:
            raise ValueError("version must be positive")
        if self.query.cursor is not None:
            raise ValueError("saved searches cannot persist a pagination cursor")
        self.query.validate()


@dataclass(frozen=True)
class AlertEvent:
    event_id: str
    saved_search_id: str
    saved_search_version: int
    canonical_id: str
    owner_id: str
    created_at: str
    status: str = "PENDING_INTERNAL"


class SQLiteSavedSearchStore:
    """Durable saved searches plus an internal, idempotent alert outbox.

    This store never sends email, SMS, push or any other external message. External
    delivery belongs behind the Factory tool/policy/approval boundary. The outbox is
    only canonical evidence that a newly qualifying listing was detected once.
    """

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
            "CREATE TABLE IF NOT EXISTS alert_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {
            int(row[0])
            for row in self._connection.execute("SELECT version FROM alert_schema_version").fetchall()
        }
        count = 0
        if 1 not in applied:
            with self._connection:
                self._connection.executescript(
                    """
                    CREATE TABLE saved_searches (
                        saved_search_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        query_json TEXT NOT NULL,
                        query_fingerprint TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        enabled INTEGER NOT NULL,
                        primed INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX idx_saved_search_owner ON saved_searches(owner_id, enabled);

                    CREATE TABLE alert_matches (
                        saved_search_id TEXT NOT NULL REFERENCES saved_searches(saved_search_id),
                        canonical_id TEXT NOT NULL,
                        first_matched_version INTEGER NOT NULL,
                        first_matched_at TEXT NOT NULL,
                        PRIMARY KEY(saved_search_id, canonical_id)
                    );

                    CREATE TABLE alert_outbox (
                        event_id TEXT PRIMARY KEY,
                        saved_search_id TEXT NOT NULL REFERENCES saved_searches(saved_search_id),
                        saved_search_version INTEGER NOT NULL,
                        canonical_id TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(saved_search_id, canonical_id)
                    );
                    CREATE INDEX idx_alert_outbox_status ON alert_outbox(status, created_at);
                    """
                )
                self._connection.execute(
                    "INSERT INTO alert_schema_version(version, applied_at) VALUES (?, ?)",
                    (1, self._now_iso()),
                )
            count += 1
        return count

    def save(self, saved: SavedSearch) -> SavedSearch:
        saved.validate()
        payload = self._serialize_query(saved.query)
        fingerprint = self._query_fingerprint(payload)
        now = self._now_iso()
        existing = self._connection.execute(
            "SELECT version, query_fingerprint, primed, created_at FROM saved_searches WHERE saved_search_id = ?",
            (saved.saved_search_id,),
        ).fetchone()

        if existing is None:
            version = saved.version
            primed = 0
            created_at = now
        else:
            previous_version = int(existing["version"])
            previous_fingerprint = str(existing["query_fingerprint"])
            query_changed = fingerprint != previous_fingerprint
            version = previous_version + 1 if query_changed else previous_version
            # A materially edited query must establish a new current-results baseline
            # before it can emit future alerts, avoiding an edit-triggered alert storm.
            primed = 0 if query_changed else int(existing["primed"])
            created_at = str(existing["created_at"])

        normalized = replace(saved, version=version)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO saved_searches(
                    saved_search_id, owner_id, name, query_json, query_fingerprint,
                    version, enabled, primed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(saved_search_id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    name = excluded.name,
                    query_json = excluded.query_json,
                    query_fingerprint = excluded.query_fingerprint,
                    version = excluded.version,
                    enabled = excluded.enabled,
                    primed = excluded.primed,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized.saved_search_id,
                    normalized.owner_id,
                    normalized.name,
                    payload,
                    fingerprint,
                    normalized.version,
                    1 if normalized.enabled else 0,
                    primed,
                    created_at,
                    now,
                ),
            )
        return normalized

    def get(self, saved_search_id: str) -> SavedSearch:
        row = self._search_row(saved_search_id)
        return self._saved_from_row(row)

    def is_primed(self, saved_search_id: str) -> bool:
        return bool(self._search_row(saved_search_id)["primed"])

    def enabled(self) -> tuple[SavedSearch, ...]:
        rows = self._connection.execute(
            "SELECT * FROM saved_searches WHERE enabled = 1 ORDER BY saved_search_id"
        ).fetchall()
        return tuple(self._saved_from_row(row) for row in rows)

    def establish_baseline(
        self,
        saved: SavedSearch,
        canonical_ids: tuple[str, ...],
        *,
        occurred_at: datetime,
    ) -> None:
        """Record already-current matches without creating notification events."""
        saved.validate()
        if occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        occurred = occurred_at.isoformat()
        with self._connection:
            for canonical_id in canonical_ids:
                if not canonical_id.strip():
                    raise ValueError("canonical_id is required")
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO alert_matches(
                        saved_search_id, canonical_id, first_matched_version, first_matched_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (saved.saved_search_id, canonical_id, saved.version, occurred),
                )
            self._connection.execute(
                "UPDATE saved_searches SET primed = 1, updated_at = ? WHERE saved_search_id = ?",
                (occurred, saved.saved_search_id),
            )

    def mark_matches(
        self,
        saved: SavedSearch,
        canonical_ids: tuple[str, ...],
        *,
        occurred_at: datetime,
    ) -> tuple[AlertEvent, ...]:
        saved.validate()
        if occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if not self.is_primed(saved.saved_search_id):
            raise RuntimeError("saved search must be primed before emitting alerts")
        occurred = occurred_at.isoformat()
        created: list[AlertEvent] = []
        with self._connection:
            for canonical_id in canonical_ids:
                if not canonical_id.strip():
                    raise ValueError("canonical_id is required")
                prior = self._connection.execute(
                    "SELECT 1 FROM alert_matches WHERE saved_search_id = ? AND canonical_id = ?",
                    (saved.saved_search_id, canonical_id),
                ).fetchone()
                if prior is not None:
                    continue
                event_id = self._event_id(saved.saved_search_id, canonical_id)
                self._connection.execute(
                    """
                    INSERT INTO alert_matches(saved_search_id, canonical_id, first_matched_version, first_matched_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (saved.saved_search_id, canonical_id, saved.version, occurred),
                )
                self._connection.execute(
                    """
                    INSERT INTO alert_outbox(
                        event_id, saved_search_id, saved_search_version, canonical_id,
                        owner_id, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        saved.saved_search_id,
                        saved.version,
                        canonical_id,
                        saved.owner_id,
                        "PENDING_INTERNAL",
                        occurred,
                    ),
                )
                created.append(
                    AlertEvent(
                        event_id=event_id,
                        saved_search_id=saved.saved_search_id,
                        saved_search_version=saved.version,
                        canonical_id=canonical_id,
                        owner_id=saved.owner_id,
                        created_at=occurred,
                    )
                )
        return tuple(created)

    def outbox(self, *, status: str = "PENDING_INTERNAL") -> tuple[AlertEvent, ...]:
        rows = self._connection.execute(
            "SELECT * FROM alert_outbox WHERE status = ? ORDER BY created_at, event_id",
            (status,),
        ).fetchall()
        return tuple(
            AlertEvent(
                event_id=str(row["event_id"]),
                saved_search_id=str(row["saved_search_id"]),
                saved_search_version=int(row["saved_search_version"]),
                canonical_id=str(row["canonical_id"]),
                owner_id=str(row["owner_id"]),
                status=str(row["status"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        )

    def _search_row(self, saved_search_id: str) -> sqlite3.Row:
        row = self._connection.execute(
            "SELECT * FROM saved_searches WHERE saved_search_id = ?",
            (saved_search_id,),
        ).fetchone()
        if row is None:
            raise KeyError(saved_search_id)
        return row

    @staticmethod
    def _serialize_query(query: SearchQuery) -> str:
        query.validate()
        if query.cursor is not None:
            raise ValueError("saved searches cannot persist a pagination cursor")
        payload = {
            "text": query.text,
            "transaction_type": query.transaction_type,
            "property_type": query.property_type,
            "city": query.city,
            "locality": query.locality,
            "geo_cell_prefix": query.geo_cell_prefix,
            "center_latitude": query.center_latitude,
            "center_longitude": query.center_longitude,
            "radius_km": query.radius_km,
            "min_price_minor": query.min_price_minor,
            "max_price_minor": query.max_price_minor,
            "bedrooms": query.bedrooms,
            "states": [state.value for state in query.states],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _deserialize_query(payload: str) -> SearchQuery:
        data = json.loads(payload)
        return SearchQuery(
            text=str(data.get("text") or ""),
            transaction_type=data.get("transaction_type"),
            property_type=data.get("property_type"),
            city=data.get("city"),
            locality=data.get("locality"),
            geo_cell_prefix=data.get("geo_cell_prefix"),
            center_latitude=data.get("center_latitude"),
            center_longitude=data.get("center_longitude"),
            radius_km=data.get("radius_km"),
            min_price_minor=data.get("min_price_minor"),
            max_price_minor=data.get("max_price_minor"),
            bedrooms=data.get("bedrooms"),
            states=tuple(ListingState(value) for value in data.get("states", ["ACTIVE", "UNDER_OFFER"])),
        )

    @classmethod
    def _saved_from_row(cls, row: sqlite3.Row) -> SavedSearch:
        return SavedSearch(
            saved_search_id=str(row["saved_search_id"]),
            owner_id=str(row["owner_id"]),
            name=str(row["name"]),
            query=cls._deserialize_query(str(row["query_json"])),
            enabled=bool(row["enabled"]),
            version=int(row["version"]),
        )

    @staticmethod
    def _query_fingerprint(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _event_id(saved_search_id: str, canonical_id: str) -> str:
        digest = hashlib.sha256(f"{saved_search_id}|{canonical_id}".encode("utf-8")).hexdigest()[:24]
        return f"ALERT-{digest}"

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


class SavedSearchEvaluator:
    def __init__(self, store: SQLiteSavedSearchStore, search: RealEstateSearchService) -> None:
        self._store = store
        self._search = search

    def evaluate(self, saved_search_id: str, *, now: datetime) -> tuple[AlertEvent, ...]:
        saved = self._store.get(saved_search_id)
        if not saved.enabled:
            return ()
        canonical_ids = self._all_matching_ids(saved.query, now=now)
        if not self._store.is_primed(saved.saved_search_id):
            self._store.establish_baseline(saved, canonical_ids, occurred_at=now)
            return ()
        return self._store.mark_matches(saved, canonical_ids, occurred_at=now)

    def evaluate_all(self, *, now: datetime) -> tuple[AlertEvent, ...]:
        events: list[AlertEvent] = []
        for saved in self._store.enabled():
            events.extend(self.evaluate(saved.saved_search_id, now=now))
        return tuple(events)

    def _all_matching_ids(self, query: SearchQuery, *, now: datetime) -> tuple[str, ...]:
        ids: list[str] = []
        cursor: str | None = None
        while True:
            page_query = replace(query, page_size=100, cursor=cursor)
            page = self._search.search(page_query, now=now)
            ids.extend(result.canonical_id for result in page.results)
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
        return tuple(ids)
