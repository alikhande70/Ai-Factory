from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re

from .contracts import ListingCandidate, ListingState, RightsBasis


_ALLOWED_RIGHTS = {
    RightsBasis.OWNER_SUBMITTED,
    RightsBasis.PARTNER_FEED,
    RightsBasis.LICENSED_DATA,
}

_ALLOWED_TRANSITIONS: dict[ListingState, set[ListingState]] = {
    ListingState.DRAFT: {ListingState.ACTIVE, ListingState.WITHDRAWN},
    ListingState.ACTIVE: {
        ListingState.UNDER_OFFER,
        ListingState.SOLD,
        ListingState.RENTED,
        ListingState.WITHDRAWN,
        ListingState.EXPIRED,
    },
    ListingState.UNDER_OFFER: {
        ListingState.ACTIVE,
        ListingState.SOLD,
        ListingState.RENTED,
        ListingState.WITHDRAWN,
        ListingState.EXPIRED,
    },
    ListingState.EXPIRED: {ListingState.ACTIVE, ListingState.WITHDRAWN},
    ListingState.SOLD: set(),
    ListingState.RENTED: set(),
    ListingState.WITHDRAWN: set(),
}


@dataclass(frozen=True)
class FreshnessPolicy:
    max_age_days: int = 30

    def validate(self) -> None:
        if self.max_age_days <= 0:
            raise ValueError("max_age_days must be positive")


def ensure_ingestion_allowed(candidate: ListingCandidate) -> None:
    candidate.validate()
    if candidate.rights_basis not in _ALLOWED_RIGHTS:
        raise PermissionError(f"ingestion rights basis is not allowed: {candidate.rights_basis.value}")


def transition_listing_state(current: ListingState, target: ListingState) -> ListingState:
    if target == current:
        return current
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid listing transition: {current.value} -> {target.value}")
    return target


def freshness_score(
    candidate: ListingCandidate,
    *,
    policy: FreshnessPolicy,
    now: datetime | None = None,
) -> float:
    policy.validate()
    ensure_ingestion_allowed(candidate)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or candidate.last_verified_at.tzinfo is None:
        raise ValueError("freshness timestamps must be timezone-aware")
    age_seconds = max(0.0, (now - candidate.last_verified_at).total_seconds())
    max_seconds = float(policy.max_age_days * 24 * 60 * 60)
    if age_seconds >= max_seconds:
        return 0.0
    return round(1.0 - (age_seconds / max_seconds), 6)


def completeness_score(candidate: ListingCandidate) -> float:
    ensure_ingestion_allowed(candidate)
    checks = (
        bool(candidate.title.strip()),
        bool(candidate.description.strip()),
        bool(candidate.city.strip()),
        bool(candidate.locality.strip()),
        bool(candidate.geo_cell.strip()),
        candidate.price_minor > 0,
        candidate.area_sqm > 0,
        candidate.bedrooms is not None,
        len(candidate.image_hashes) >= 3,
    )
    return round(sum(checks) / len(checks), 6)


def _normalize_text(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[^\w\s-]", "", value)
    return re.sub(r"\s+", " ", value)


def duplicate_fingerprint(candidate: ListingCandidate) -> str:
    ensure_ingestion_allowed(candidate)
    # Intentionally excludes publisher/source identifiers: duplicate grouping asks
    # whether two source records may describe the same physical opportunity.
    rounded_area = round(candidate.area_sqm / 5.0) * 5
    stable_image = min(candidate.image_hashes) if candidate.image_hashes else "no-image"
    parts = (
        _normalize_text(candidate.transaction_type),
        _normalize_text(candidate.property_type),
        _normalize_text(candidate.city),
        _normalize_text(candidate.locality),
        _normalize_text(candidate.geo_cell),
        str(rounded_area),
        str(candidate.bedrooms),
        stable_image,
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
