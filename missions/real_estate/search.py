from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import base64
import hashlib
import json
import re

from .contracts import ListingState, SearchSignals
from .geo import GeoPoint, SQLiteGeoIndex
from .integrity import FreshnessPolicy, completeness_score, freshness_score
from .inventory import InventoryQuery, SQLiteInventoryStore
from .ranking import rank_listing


_TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)


@dataclass(frozen=True)
class SearchQuery:
    text: str = ""
    transaction_type: str | None = None
    property_type: str | None = None
    city: str | None = None
    locality: str | None = None
    geo_cell_prefix: str | None = None
    center_latitude: float | None = None
    center_longitude: float | None = None
    radius_km: float | None = None
    min_price_minor: int | None = None
    max_price_minor: int | None = None
    bedrooms: int | None = None
    states: tuple[ListingState, ...] = (ListingState.ACTIVE, ListingState.UNDER_OFFER)
    page_size: int = 20
    cursor: str | None = None

    def validate(self) -> None:
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        InventoryQuery(
            transaction_type=self.transaction_type,
            property_type=self.property_type,
            city=self.city,
            locality=self.locality,
            min_price_minor=self.min_price_minor,
            max_price_minor=self.max_price_minor,
            bedrooms=self.bedrooms,
            states=self.states,
        ).validate()
        if self.geo_cell_prefix is not None and not self.geo_cell_prefix.strip():
            raise ValueError("geo_cell_prefix cannot be blank")
        geo_values = (self.center_latitude, self.center_longitude, self.radius_km)
        if any(value is not None for value in geo_values) and not all(value is not None for value in geo_values):
            raise ValueError("center_latitude, center_longitude and radius_km must be provided together")
        if self.center_latitude is not None:
            GeoPoint(self.center_latitude, self.center_longitude).validate()  # type: ignore[arg-type]
            if self.radius_km is None or self.radius_km <= 0.0:
                raise ValueError("radius_km must be positive")


@dataclass(frozen=True)
class SearchResult:
    canonical_id: str
    score: float
    title: str
    city: str
    locality: str
    geo_cell: str
    price_minor: int
    area_sqm: float
    bedrooms: int | None
    last_verified_at: str
    reasons: tuple[str, ...]
    distance_km: float | None = None


@dataclass(frozen=True)
class SearchPage:
    results: tuple[SearchResult, ...]
    next_cursor: str | None
    total_candidates: int


class RealEstateSearchService:
    """Deterministic search over the canonical inventory projection.

    Duplicate collapse is inherited from canonical inventory: a duplicate group yields
    at most one result. Exact radius filtering is delegated to a separate bounded geo
    index so spatial concerns cannot mutate listing lifecycle, rights or trust state.
    """

    def __init__(
        self,
        store: SQLiteInventoryStore,
        *,
        freshness_policy: FreshnessPolicy | None = None,
        geo_index: SQLiteGeoIndex | None = None,
    ) -> None:
        self._store = store
        self._freshness_policy = freshness_policy or FreshnessPolicy()
        self._geo_index = geo_index

    def search(self, query: SearchQuery, *, now: datetime) -> SearchPage:
        query.validate()
        if now.tzinfo is None:
            raise ValueError("search now must be timezone-aware")

        inventory_query = InventoryQuery(
            transaction_type=query.transaction_type,
            property_type=query.property_type,
            city=query.city,
            locality=query.locality,
            min_price_minor=query.min_price_minor,
            max_price_minor=query.max_price_minor,
            bedrooms=query.bedrooms,
            states=query.states,
        )
        canonical_rows = self._store.query(inventory_query)
        signature = self._query_signature(query)
        after = self._decode_cursor(query.cursor, expected_signature=signature) if query.cursor else None

        distance_by_id: dict[str, float] | None = None
        if query.radius_km is not None:
            if self._geo_index is None:
                raise RuntimeError("radius search requires a geo index")
            center = GeoPoint(float(query.center_latitude), float(query.center_longitude))
            hits = self._geo_index.within_radius(center, radius_km=query.radius_km)
            distance_by_id = {hit.canonical_id: hit.distance_km for hit in hits}

        ranked: list[SearchResult] = []
        for row in canonical_rows:
            canonical_id = str(row["canonical_id"])
            geo_cell = str(row["geo_cell"])
            if query.geo_cell_prefix is not None and not geo_cell.startswith(query.geo_cell_prefix):
                continue
            if distance_by_id is not None and canonical_id not in distance_by_id:
                continue

            source = self._store.source_record(str(row["active_source_version_id"]))
            candidate = self._store._candidate_from_source(
                source,
                state=ListingState(str(row["state"])),
            )
            relevance = self._text_relevance(
                query.text,
                candidate.title,
                candidate.description,
                candidate.city,
                candidate.locality,
            )
            if query.text.strip() and relevance <= 0.0:
                continue

            trust = self._store.publisher_trust(candidate.publisher_id)
            trust_score = trust.score if trust is not None else 0.0
            signals = SearchSignals(
                relevance=relevance,
                freshness=freshness_score(candidate, policy=self._freshness_policy, now=now),
                completeness=completeness_score(candidate),
                publisher_trust=trust_score,
            )
            decision = rank_listing(candidate, signals)
            if not decision.eligible:
                continue

            result = SearchResult(
                canonical_id=canonical_id,
                score=decision.score,
                title=str(row["title"]),
                city=str(row["city"]),
                locality=str(row["locality"]),
                geo_cell=geo_cell,
                price_minor=int(row["price_minor"]),
                area_sqm=float(row["area_sqm"]),
                bedrooms=int(row["bedrooms"]) if row["bedrooms"] is not None else None,
                last_verified_at=str(row["last_verified_at"]),
                reasons=decision.reasons,
                distance_km=distance_by_id.get(canonical_id) if distance_by_id is not None else None,
            )
            if after is None or self._is_after(result, after):
                ranked.append(result)

        ranked.sort(key=self._sort_key)
        total_candidates = len(ranked)
        page_items = ranked[: query.page_size]
        next_cursor = None
        if len(ranked) > query.page_size and page_items:
            next_cursor = self._encode_cursor(page_items[-1], signature)
        return SearchPage(tuple(page_items), next_cursor, total_candidates)

    @staticmethod
    def _normalize_tokens(value: str) -> tuple[str, ...]:
        return tuple(token.casefold() for token in _TOKEN_RE.findall(value))

    @classmethod
    def _text_relevance(cls, query: str, title: str, description: str, city: str, locality: str) -> float:
        query_tokens = set(cls._normalize_tokens(query))
        if not query_tokens:
            return 1.0
        title_tokens = set(cls._normalize_tokens(title))
        description_tokens = set(cls._normalize_tokens(description))
        location_tokens = set(cls._normalize_tokens(f"{city} {locality}"))
        matched = 0.0
        for token in query_tokens:
            if token in title_tokens:
                matched += 1.0
            elif token in location_tokens:
                matched += 0.8
            elif token in description_tokens:
                matched += 0.5
        return round(min(1.0, matched / len(query_tokens)), 6)

    @staticmethod
    def _sort_key(result: SearchResult) -> tuple[float, float, str]:
        verified_ts = datetime.fromisoformat(result.last_verified_at).timestamp()
        return (-result.score, -verified_ts, result.canonical_id)

    @classmethod
    def _cursor_key(cls, result: SearchResult) -> tuple[float, float, str]:
        return cls._sort_key(result)

    @classmethod
    def _is_after(cls, result: SearchResult, cursor: tuple[float, float, str]) -> bool:
        return cls._cursor_key(result) > cursor

    @staticmethod
    def _query_signature(query: SearchQuery) -> str:
        payload = {
            "text": query.text.casefold().strip(),
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
            "page_size": query.page_size,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]

    @classmethod
    def _encode_cursor(cls, result: SearchResult, signature: str) -> str:
        payload = {
            "v": 1,
            "sig": signature,
            "score": result.score,
            "verified": result.last_verified_at,
            "id": result.canonical_id,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @classmethod
    def _decode_cursor(cls, cursor: str, *, expected_signature: str) -> tuple[float, float, str]:
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
            if payload.get("v") != 1 or payload.get("sig") != expected_signature:
                raise ValueError("cursor does not belong to this search query")
            result = SearchResult(
                canonical_id=str(payload["id"]),
                score=float(payload["score"]),
                title="",
                city="",
                locality="",
                geo_cell="",
                price_minor=0,
                area_sqm=1.0,
                bedrooms=None,
                last_verified_at=str(payload["verified"]),
                reasons=(),
            )
            return cls._cursor_key(result)
        except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc) == "cursor does not belong to this search query":
                raise
            raise ValueError("invalid search cursor") from exc
