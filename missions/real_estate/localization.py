from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .presentation import ConsumerListingProjection


_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_SUPPORTED_CURRENCIES = {"IRR", "EUR", "USD"}


class TextDirection(str, Enum):
    LTR = "LTR"
    RTL = "RTL"


@dataclass(frozen=True)
class LocaleContext:
    locale: str
    language: str
    numbering_system: str
    direction: TextDirection
    timezone: str
    currency_code: str

    def validate(self) -> None:
        if self.locale not in {"fa-IR", "en-US"}:
            raise ValueError(f"unsupported locale: {self.locale}")
        expected = {
            "fa-IR": ("fa", "arabext", TextDirection.RTL),
            "en-US": ("en", "latn", TextDirection.LTR),
        }[self.locale]
        if (self.language, self.numbering_system, self.direction) != expected:
            raise ValueError("locale profile fields are inconsistent")
        if self.currency_code not in _SUPPORTED_CURRENCIES:
            raise ValueError("currency_code must be explicit and supported")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {self.timezone}") from exc


@dataclass(frozen=True)
class LocalizedMessage:
    code: str
    text: str
    fallback_used: bool


@dataclass(frozen=True)
class LocalizedConsumerListing:
    canonical_id: str
    canonical_url: str | None
    locale: str
    direction: TextDirection
    title: str
    location_text: str
    price_text: str
    area_text: str
    bedrooms_text: str
    last_verified_text: str
    state: str
    trust_code: str
    verification_badge: bool
    message_codes: tuple[str, ...]
    messages: tuple[LocalizedMessage, ...]


_MESSAGES: dict[str, dict[str, str]] = {
    "fa-IR": {
        "LISTING_STALE": "این آگهی نیاز به بررسی تازگی دارد.",
        "DISCLOSURE_INCOMPLETE": "بخشی از اطلاعات آگهی کامل نیست.",
        "TRUST_REVIEW_PENDING": "اطلاعات اعتماد این آگهی در حال بررسی است.",
        "TRUST_EVIDENCE_AVAILABLE": "برای ناشر شواهد بررسی‌شده ثبت شده است.",
        "ALERT_NOT_EXTERNALLY_DELIVERED": "هشدار فقط داخل سیستم ثبت شده و تحویل خارجی تأیید نشده است.",
        "ALERT_DELIVERY_UNVERIFIED": "وضعیت تحویل خارجی هشدار تأیید نشده است.",
        "ANOMALY_REVIEW_REQUIRED": "این مورد برای بررسی انسانی علامت‌گذاری شده است.",
        "ANOMALY_EVIDENCE_STALE": "شواهد این بررسی نسبت به وضعیت فعلی قدیمی شده است.",
    },
    "en-US": {
        "LISTING_STALE": "This listing needs a freshness review.",
        "DISCLOSURE_INCOMPLETE": "Some listing disclosures are incomplete.",
        "TRUST_REVIEW_PENDING": "Trust information for this listing is under review.",
        "TRUST_EVIDENCE_AVAILABLE": "Reviewed publisher trust evidence is available.",
        "ALERT_NOT_EXTERNALLY_DELIVERED": "The alert exists internally; external delivery is not confirmed.",
        "ALERT_DELIVERY_UNVERIFIED": "External alert delivery is unverified.",
        "ANOMALY_REVIEW_REQUIRED": "This item is flagged for human review.",
        "ANOMALY_EVIDENCE_STALE": "The review evidence is stale relative to current data.",
    },
}


class RealEstateMarketAdapter:
    """Formats qualified projections without changing domain semantics."""

    def __init__(self, context: LocaleContext) -> None:
        context.validate()
        self.context = context
        self._timezone = ZoneInfo(context.timezone)

    def localize_message(self, code: str) -> LocalizedMessage:
        catalog = _MESSAGES[self.context.locale]
        if code in catalog:
            return LocalizedMessage(code=code, text=catalog[code], fallback_used=False)
        # Deterministic, observable fallback: preserve the code rather than inventing copy.
        return LocalizedMessage(code=code, text=f"[{code}]", fallback_used=True)

    def format_integer(self, value: int) -> str:
        if not isinstance(value, int):
            raise TypeError("format_integer requires an integer canonical value")
        grouped = f"{value:,}"
        if self.context.numbering_system == "arabext":
            return grouped.translate(_PERSIAN_DIGITS).replace(",", "٬")
        return grouped

    def format_decimal(self, value: float, *, places: int = 1) -> str:
        if places < 0 or places > 6:
            raise ValueError("places must be between 0 and 6")
        rendered = f"{value:,.{places}f}"
        if self.context.numbering_system == "arabext":
            return rendered.translate(_PERSIAN_DIGITS).replace(",", "٬").replace(".", "٫")
        return rendered

    def format_amount(self, minor_value: int) -> str:
        if minor_value < 0:
            raise ValueError("amount cannot be negative")
        number = self.format_integer(minor_value)
        currency = self.context.currency_code
        if self.context.locale == "fa-IR":
            labels = {"IRR": "ریال", "EUR": "یورو", "USD": "دلار آمریکا"}
            return f"{number} {labels[currency]}"
        symbols = {"IRR": "IRR", "EUR": "€", "USD": "$"}
        symbol = symbols[currency]
        return f"{symbol}{number}" if currency in {"EUR", "USD"} else f"{number} {symbol}"

    def format_datetime(self, value: datetime) -> str:
        if value.tzinfo is None:
            raise ValueError("canonical datetime must be timezone-aware")
        local = value.astimezone(self._timezone)
        rendered = local.strftime("%Y-%m-%d %H:%M %Z")
        if self.context.numbering_system == "arabext":
            rendered = rendered.translate(_PERSIAN_DIGITS)
        return rendered

    def localize_consumer_listing(
        self,
        projection: ConsumerListingProjection,
        *,
        canonical_url: str | None = None,
    ) -> LocalizedConsumerListing:
        verified = datetime.fromisoformat(projection.last_verified_at)
        messages = tuple(self.localize_message(code) for code in projection.message_codes)
        if self.context.locale == "fa-IR":
            location = f"{projection.city}، {projection.locality}"
            area = f"{self.format_decimal(projection.area_sqm)} متر مربع"
            bedrooms = "نامشخص" if projection.bedrooms is None else f"{self.format_integer(projection.bedrooms)} خواب"
        else:
            location = f"{projection.locality}, {projection.city}"
            area = f"{self.format_decimal(projection.area_sqm)} m²"
            bedrooms = "Unknown" if projection.bedrooms is None else f"{self.format_integer(projection.bedrooms)} bed"
        return LocalizedConsumerListing(
            canonical_id=projection.canonical_id,
            canonical_url=canonical_url,
            locale=self.context.locale,
            direction=self.context.direction,
            title=projection.title,
            location_text=location,
            price_text=self.format_amount(projection.price_minor),
            area_text=area,
            bedrooms_text=bedrooms,
            last_verified_text=self.format_datetime(verified),
            state=projection.state,
            trust_code=projection.trust_code.value,
            verification_badge=projection.verification_badge,
            message_codes=projection.message_codes,
            messages=messages,
        )
