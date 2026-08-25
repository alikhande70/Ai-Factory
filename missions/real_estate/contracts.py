from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RightsBasis(str, Enum):
    OWNER_SUBMITTED = "OWNER_SUBMITTED"
    PARTNER_FEED = "PARTNER_FEED"
    LICENSED_DATA = "LICENSED_DATA"
    UNAUTHORIZED_SCRAPE = "UNAUTHORIZED_SCRAPE"


class ListingState(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    UNDER_OFFER = "UNDER_OFFER"
    SOLD = "SOLD"
    RENTED = "RENTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class ListingCandidate:
    listing_id: str
    source_ref: str
    publisher_id: str
    rights_basis: RightsBasis
    transaction_type: str
    property_type: str
    city: str
    locality: str
    geo_cell: str
    price_minor: int
    area_sqm: float
    bedrooms: int | None
    title: str
    description: str
    image_hashes: tuple[str, ...]
    source_updated_at: datetime
    last_verified_at: datetime
    latitude: float | None = None
    longitude: float | None = None
    state: ListingState = ListingState.DRAFT

    def validate(self) -> None:
        if not self.listing_id.strip():
            raise ValueError("listing_id is required")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        if not self.publisher_id.strip():
            raise ValueError("publisher_id is required")
        if self.price_minor < 0:
            raise ValueError("price_minor must be non-negative")
        if self.area_sqm <= 0:
            raise ValueError("area_sqm must be positive")
        if self.bedrooms is not None and self.bedrooms < 0:
            raise ValueError("bedrooms must be non-negative")
        if self.last_verified_at < self.source_updated_at:
            raise ValueError("last_verified_at cannot predate source_updated_at")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.latitude is not None and not -90.0 <= self.latitude <= 90.0:
            raise ValueError("latitude must be between -90 and 90")
        if self.longitude is not None and not -180.0 <= self.longitude <= 180.0:
            raise ValueError("longitude must be between -180 and 180")


@dataclass(frozen=True)
class SearchSignals:
    relevance: float
    freshness: float
    completeness: float
    publisher_trust: float
    anomaly_penalty: float = 0.0

    def validate(self) -> None:
        for name, value in (
            ("relevance", self.relevance),
            ("freshness", self.freshness),
            ("completeness", self.completeness),
            ("publisher_trust", self.publisher_trust),
            ("anomaly_penalty", self.anomaly_penalty),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
