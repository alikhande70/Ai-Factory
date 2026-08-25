from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .presentation import FreshnessPresentation, RealEstatePresentationService, TrustPresentation


@dataclass(frozen=True)
class ConsumerListingCardProjection:
    canonical_id: str
    title: str
    city: str
    locality: str
    price_minor: int
    area_sqm: float
    bedrooms: int | None
    freshness_code: FreshnessPresentation
    trust_code: TrustPresentation
    verification_badge: bool
    message_codes: tuple[str, ...]


def project_consumer_card(
    service: RealEstatePresentationService,
    canonical_id: str,
    *,
    now: datetime,
) -> ConsumerListingCardProjection:
    """Create the compact card only from the qualified detail projection.

    Keeping the card as a strict subset prevents list/search surfaces from inventing
    stronger trust or freshness claims than the corresponding detail surface.
    """

    detail = service.consumer_listing(canonical_id, now=now)
    return ConsumerListingCardProjection(
        canonical_id=detail.canonical_id,
        title=detail.title,
        city=detail.city,
        locality=detail.locality,
        price_minor=detail.price_minor,
        area_sqm=detail.area_sqm,
        bedrooms=detail.bedrooms,
        freshness_code=detail.freshness_code,
        trust_code=detail.trust_code,
        verification_badge=detail.verification_badge,
        message_codes=detail.message_codes,
    )
