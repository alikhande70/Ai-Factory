from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json

from .alerts import AlertEvent
from .anomalies import DuplicatePriceDivergenceDetector, FindingSeverity
from .contracts import ListingCandidate, ListingState, RightsBasis
from .integrity import FreshnessPolicy, allowed_listing_transitions, completeness_score, freshness_score
from .inventory import SQLiteInventoryStore
from .review_queue import ReviewCase, ReviewStatus, SQLiteTrustReviewStore


_ALLOWED_RIGHTS = {
    RightsBasis.OWNER_SUBMITTED,
    RightsBasis.PARTNER_FEED,
    RightsBasis.LICENSED_DATA,
}


class FreshnessPresentation(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"


class TrustPresentation(str, Enum):
    UNKNOWN = "UNKNOWN"
    EVIDENCE_AVAILABLE = "EVIDENCE_AVAILABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class EvidenceCurrency(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"


class DeliveryPresentation(str, Enum):
    INTERNAL_EVENT_ONLY = "INTERNAL_EVENT_ONLY"
    EXTERNAL_DELIVERY_CONFIRMED = "EXTERNAL_DELIVERY_CONFIRMED"


@dataclass(frozen=True)
class ConsumerListingProjection:
    canonical_id: str
    title: str
    city: str
    locality: str
    price_minor: int
    area_sqm: float
    bedrooms: int | None
    state: str
    last_verified_at: str
    freshness_code: FreshnessPresentation
    disclosure_score: float
    source_count: int
    rights_bases: tuple[str, ...]
    trust_code: TrustPresentation
    verification_badge: bool
    message_codes: tuple[str, ...]


@dataclass(frozen=True)
class PublisherSubmissionProjection:
    listing_id: str
    source_ref: str
    rights_basis: str
    rights_accepted: bool
    submitted_state: str
    missing_disclosures: tuple[str, ...]
    allowed_lifecycle_actions: tuple[str, ...]
    blocking_codes: tuple[str, ...]


@dataclass(frozen=True)
class PublisherListingProjection:
    canonical_id: str
    listing_id: str
    source_ref: str
    rights_basis: str
    rights_accepted: bool
    state: str
    missing_disclosures: tuple[str, ...]
    allowed_lifecycle_actions: tuple[str, ...]
    message_codes: tuple[str, ...]


@dataclass(frozen=True)
class AlertStatusProjection:
    event_id: str
    saved_search_id: str
    canonical_id: str
    internal_status: str
    delivery_code: DeliveryPresentation
    message_codes: tuple[str, ...]


@dataclass(frozen=True)
class OperatorReviewProjection:
    case_id: str
    finding_id: str
    canonical_id: str
    severity: str
    status: str
    assigned_reviewer: str | None
    evidence_refs: tuple[str, ...]
    evidence_currency: EvidenceCurrency
    message_codes: tuple[str, ...]


class RealEstatePresentationService:
    """Read-only projections for consumer, publisher and operator surfaces.

    The service intentionally exposes no mutation methods. It translates canonical
    domain state into typed presentation codes and never creates trust, fraud,
    lifecycle, rights or external-delivery facts.
    """

    def __init__(
        self,
        inventory: SQLiteInventoryStore,
        *,
        review_store: SQLiteTrustReviewStore | None = None,
        detector: DuplicatePriceDivergenceDetector | None = None,
        freshness_policy: FreshnessPolicy | None = None,
    ) -> None:
        self._inventory = inventory
        self._review_store = review_store
        self._detector = detector or DuplicatePriceDivergenceDetector()
        self._freshness_policy = freshness_policy or FreshnessPolicy()

    def consumer_listing(self, canonical_id: str, *, now: datetime) -> ConsumerListingProjection:
        if now.tzinfo is None:
            raise ValueError("presentation time must be timezone-aware")
        canonical = self._inventory.canonical(canonical_id)
        active_source = self._inventory.source_record(str(canonical["active_source_version_id"]))
        candidate = self._candidate(active_source, ListingState(str(canonical["state"])))
        members = self._inventory.source_members(canonical_id)

        freshness = freshness_score(candidate, policy=self._freshness_policy, now=now)
        freshness_code = FreshnessPresentation.FRESH if freshness > 0.0 else FreshnessPresentation.STALE
        disclosure = completeness_score(candidate)
        trust_evidence = self._inventory.publisher_trust(candidate.publisher_id)
        trust_code = TrustPresentation.EVIDENCE_AVAILABLE if trust_evidence is not None else TrustPresentation.UNKNOWN
        messages: list[str] = []

        if freshness_code == FreshnessPresentation.STALE:
            messages.append("LISTING_STALE")
        if disclosure < 1.0:
            messages.append("DISCLOSURE_INCOMPLETE")
        if self._has_active_high_impact_review(canonical_id):
            trust_code = TrustPresentation.NEEDS_REVIEW
            messages.append("TRUST_REVIEW_PENDING")

        # Trust score/evidence is not an explicit verification-badge grant.
        verification_badge = False
        if trust_evidence is not None:
            messages.append("TRUST_EVIDENCE_AVAILABLE")

        return ConsumerListingProjection(
            canonical_id=canonical_id,
            title=str(canonical["title"]),
            city=str(canonical["city"]),
            locality=str(canonical["locality"]),
            price_minor=int(canonical["price_minor"]),
            area_sqm=float(canonical["area_sqm"]),
            bedrooms=int(canonical["bedrooms"]) if canonical["bedrooms"] is not None else None,
            state=str(canonical["state"]),
            last_verified_at=str(canonical["last_verified_at"]),
            freshness_code=freshness_code,
            disclosure_score=disclosure,
            source_count=len(members),
            rights_bases=tuple(sorted({str(row["rights_basis"]) for row in members})),
            trust_code=trust_code,
            verification_badge=verification_badge,
            message_codes=tuple(messages),
        )

    @staticmethod
    def publisher_submission(candidate: ListingCandidate) -> PublisherSubmissionProjection:
        candidate.validate()
        rights_accepted = candidate.rights_basis in _ALLOWED_RIGHTS
        missing = RealEstatePresentationService._candidate_missing_disclosures(candidate)
        blockers: list[str] = []
        if not rights_accepted:
            blockers.append("RIGHTS_BASIS_REJECTED")
        if missing:
            blockers.append("DISCLOSURE_ACTION_REQUIRED")
        actions = () if not rights_accepted else tuple(
            item.value for item in allowed_listing_transitions(candidate.state)
        )
        return PublisherSubmissionProjection(
            listing_id=candidate.listing_id,
            source_ref=candidate.source_ref,
            rights_basis=candidate.rights_basis.value,
            rights_accepted=rights_accepted,
            submitted_state=candidate.state.value,
            missing_disclosures=missing,
            allowed_lifecycle_actions=actions,
            blocking_codes=tuple(blockers),
        )

    def publisher_listing(self, canonical_id: str) -> PublisherListingProjection:
        canonical = self._inventory.canonical(canonical_id)
        source = self._inventory.source_record(str(canonical["active_source_version_id"]))
        state = ListingState(str(canonical["state"]))
        rights = RightsBasis(str(source["rights_basis"]))
        missing = self._missing_disclosures(source)
        rights_accepted = rights in _ALLOWED_RIGHTS
        messages: list[str] = []
        if not rights_accepted:
            messages.append("RIGHTS_BASIS_REJECTED")
        if missing:
            messages.append("DISCLOSURE_ACTION_REQUIRED")

        return PublisherListingProjection(
            canonical_id=canonical_id,
            listing_id=str(source["listing_id"]),
            source_ref=str(source["source_ref"]),
            rights_basis=rights.value,
            rights_accepted=rights_accepted,
            state=state.value,
            missing_disclosures=missing,
            allowed_lifecycle_actions=tuple(item.value for item in allowed_listing_transitions(state)),
            message_codes=tuple(messages),
        )

    @staticmethod
    def alert_status(event: AlertEvent) -> AlertStatusProjection:
        if event.status == "PENDING_INTERNAL":
            delivery = DeliveryPresentation.INTERNAL_EVENT_ONLY
            messages = ("ALERT_NOT_EXTERNALLY_DELIVERED",)
        else:
            delivery = DeliveryPresentation.INTERNAL_EVENT_ONLY
            messages = ("ALERT_DELIVERY_UNVERIFIED",)
        return AlertStatusProjection(
            event_id=event.event_id,
            saved_search_id=event.saved_search_id,
            canonical_id=event.canonical_id,
            internal_status=event.status,
            delivery_code=delivery,
            message_codes=messages,
        )

    def operator_review(self, case: ReviewCase) -> OperatorReviewProjection:
        current = self._detector.detect(self._inventory, case.finding.canonical_id)
        evidence_currency = (
            EvidenceCurrency.CURRENT
            if current is not None and current.evidence_fingerprint == case.finding.evidence_fingerprint
            else EvidenceCurrency.STALE
        )
        messages = ["ANOMALY_REVIEW_REQUIRED"]
        if evidence_currency == EvidenceCurrency.STALE:
            messages.append("ANOMALY_EVIDENCE_STALE")
        return OperatorReviewProjection(
            case_id=case.case_id,
            finding_id=case.finding.finding_id,
            canonical_id=case.finding.canonical_id,
            severity=case.finding.severity.value,
            status=case.status.value,
            assigned_reviewer=case.assigned_reviewer,
            evidence_refs=case.finding.evidence_refs,
            evidence_currency=evidence_currency,
            message_codes=tuple(messages),
        )

    def _has_active_high_impact_review(self, canonical_id: str) -> bool:
        if self._review_store is None:
            return False
        for case in self._review_store.open_cases():
            if (
                case.finding.canonical_id == canonical_id
                and case.status in {ReviewStatus.OPEN, ReviewStatus.IN_REVIEW}
                and case.finding.severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL}
            ):
                return True
        return False

    @staticmethod
    def _candidate_missing_disclosures(candidate: ListingCandidate) -> tuple[str, ...]:
        missing: list[str] = []
        for key, value in (
            ("TITLE", candidate.title),
            ("DESCRIPTION", candidate.description),
            ("CITY", candidate.city),
            ("LOCALITY", candidate.locality),
            ("GEO_CELL", candidate.geo_cell),
        ):
            if not value.strip():
                missing.append(key)
        if candidate.price_minor <= 0:
            missing.append("PRICE")
        if candidate.bedrooms is None:
            missing.append("BEDROOMS")
        if len(candidate.image_hashes) < 3:
            missing.append("IMAGES")
        return tuple(missing)

    @staticmethod
    def _missing_disclosures(source: dict[str, object]) -> tuple[str, ...]:
        return RealEstatePresentationService._candidate_missing_disclosures(
            RealEstatePresentationService._candidate(
                source, ListingState(str(source["submitted_state"]))
            )
        )

    @staticmethod
    def _candidate(source: dict[str, object], state: ListingState) -> ListingCandidate:
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
