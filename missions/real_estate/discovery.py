from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import html
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from .contracts import ListingState, RightsBasis
from .inventory import InventoryQuery, SQLiteInventoryStore
from .presentation import FreshnessPresentation, RealEstatePresentationService


_CANONICAL_ID_RE = re.compile(r"^CAN-[a-f0-9]{20}$")
_TAG_RE = re.compile(r"<[^>]*>")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_WHITESPACE_RE = re.compile(r"\s+")
_ALLOWED_PUBLIC_RIGHTS = {
    RightsBasis.OWNER_SUBMITTED.value,
    RightsBasis.PARTNER_FEED.value,
    RightsBasis.LICENSED_DATA.value,
}
STRUCTURED_DATA_PROFILE = "schema.org-v30.0"
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"


class NoIndexReason(str, Enum):
    STATE_NOT_PUBLIC = "STATE_NOT_PUBLIC"
    STALE = "STALE"
    RIGHTS_NOT_PUBLIC = "RIGHTS_NOT_PUBLIC"


@dataclass(frozen=True)
class IndexEligibility:
    indexable: bool
    reasons: tuple[NoIndexReason, ...]


@dataclass(frozen=True)
class DiscoveryDocument:
    canonical_id: str
    route_path: str
    canonical_url: str
    indexable: bool
    robots_directive: str
    noindex_reasons: tuple[str, ...]
    title: str
    description: str
    city: str
    locality: str
    price_minor: int
    lastmod: str
    structured_data_profile: str
    structured_data: dict[str, object]


@dataclass(frozen=True)
class SitemapEntry:
    canonical_id: str
    loc: str
    lastmod: str


class IndexEligibilityPolicy:
    """Pure policy for deciding whether canonical inventory may be publicly indexed."""

    PUBLIC_STATES = {ListingState.ACTIVE.value, ListingState.UNDER_OFFER.value}

    @classmethod
    def evaluate(
        cls,
        *,
        state: str,
        freshness: FreshnessPresentation,
        rights_bases: tuple[str, ...],
    ) -> IndexEligibility:
        reasons: list[NoIndexReason] = []
        if state not in cls.PUBLIC_STATES:
            reasons.append(NoIndexReason.STATE_NOT_PUBLIC)
        if freshness == FreshnessPresentation.STALE:
            reasons.append(NoIndexReason.STALE)
        if not rights_bases or any(item not in _ALLOWED_PUBLIC_RIGHTS for item in rights_bases):
            reasons.append(NoIndexReason.RIGHTS_NOT_PUBLIC)
        return IndexEligibility(indexable=not reasons, reasons=tuple(reasons))


class RealEstateDiscoveryService:
    """Read-only public discovery projections derived from canonical inventory.

    SEO/discovery state is never stored as an independent listing truth source. A
    document is rebuilt from canonical state so duplicate sources cannot create
    alternate public listing URLs and stale/lifecycle changes immediately affect
    index eligibility.
    """

    def __init__(
        self,
        inventory: SQLiteInventoryStore,
        *,
        public_base_url: str,
        presentation: RealEstatePresentationService | None = None,
    ) -> None:
        self._inventory = inventory
        self._base_url = self._validate_base_url(public_base_url)
        self._presentation = presentation or RealEstatePresentationService(inventory)

    def listing_document(self, canonical_id: str, *, now: datetime) -> DiscoveryDocument:
        route = self.route_for(canonical_id)
        detail = self._presentation.consumer_listing(canonical_id, now=now)
        canonical = self._inventory.canonical(canonical_id)
        eligibility = IndexEligibilityPolicy.evaluate(
            state=detail.state,
            freshness=detail.freshness_code,
            rights_bases=detail.rights_bases,
        )
        title = self._plain_text(detail.title, limit=70)
        raw_description = str(canonical["description"])
        description = self._plain_text(raw_description, limit=160)
        canonical_url = f"{self._base_url}{route}"
        structured_data: dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "RealEstateListing",
            "url": canonical_url,
            "name": title,
            "description": description,
        }
        return DiscoveryDocument(
            canonical_id=canonical_id,
            route_path=route,
            canonical_url=canonical_url,
            indexable=eligibility.indexable,
            robots_directive="index,follow" if eligibility.indexable else "noindex,follow",
            noindex_reasons=tuple(reason.value for reason in eligibility.reasons),
            title=title,
            description=description,
            city=detail.city,
            locality=detail.locality,
            price_minor=detail.price_minor,
            lastmod=str(canonical["updated_at"]),
            structured_data_profile=STRUCTURED_DATA_PROFILE,
            structured_data=structured_data,
        )

    def sitemap(self, *, now: datetime) -> tuple[SitemapEntry, ...]:
        rows = self._inventory.query(
            InventoryQuery(states=(ListingState.ACTIVE, ListingState.UNDER_OFFER))
        )
        entries: list[SitemapEntry] = []
        for row in rows:
            canonical_id = str(row["canonical_id"])
            document = self.listing_document(canonical_id, now=now)
            if document.indexable:
                entries.append(
                    SitemapEntry(
                        canonical_id=canonical_id,
                        loc=document.canonical_url,
                        lastmod=document.lastmod,
                    )
                )
        return tuple(sorted(entries, key=lambda entry: entry.loc))

    @staticmethod
    def render_sitemap_xml(entries: tuple[SitemapEntry, ...]) -> str:
        """Render sitemap XML from a qualified entry projection.

        ElementTree performs XML escaping for URLs. Only already-qualified entries
        should reach this renderer; it has no inventory/policy authority itself.
        """

        ET.register_namespace("", SITEMAP_NAMESPACE)
        root = ET.Element(f"{{{SITEMAP_NAMESPACE}}}urlset")
        previous_loc: str | None = None
        for entry in sorted(entries, key=lambda item: item.loc):
            if previous_loc == entry.loc:
                raise ValueError("duplicate sitemap loc is not allowed")
            previous_loc = entry.loc
            url = ET.SubElement(root, f"{{{SITEMAP_NAMESPACE}}}url")
            ET.SubElement(url, f"{{{SITEMAP_NAMESPACE}}}loc").text = entry.loc
            ET.SubElement(url, f"{{{SITEMAP_NAMESPACE}}}lastmod").text = entry.lastmod
        return ET.tostring(root, encoding="unicode", xml_declaration=False)

    @staticmethod
    def route_for(canonical_id: str) -> str:
        if not _CANONICAL_ID_RE.fullmatch(canonical_id):
            raise ValueError("canonical_id is not a valid public route identifier")
        return f"/listing/{canonical_id}"

    @staticmethod
    def _validate_base_url(value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("public_base_url must be an HTTPS origin without credentials, query or fragment")
        path = parsed.path.rstrip("/")
        return f"https://{parsed.netloc}{path}"

    @staticmethod
    def _plain_text(value: str, *, limit: int) -> str:
        text = html.unescape(value)
        text = _TAG_RE.sub(" ", text)
        text = _CONTROL_RE.sub(" ", text)
        text = _WHITESPACE_RE.sub(" ", text).strip()
        return text[:limit].rstrip()
