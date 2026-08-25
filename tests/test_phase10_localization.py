from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from missions.real_estate.contracts import ListingCandidate, ListingState, RightsBasis
from missions.real_estate.discovery import RealEstateDiscoveryService
from missions.real_estate.inventory import SQLiteInventoryStore
from missions.real_estate.localization import LocaleContext, RealEstateMarketAdapter, TextDirection
from missions.real_estate.presentation import RealEstatePresentationService


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def candidate() -> ListingCandidate:
    return ListingCandidate(
        listing_id="L1",
        source_ref="owner://1",
        publisher_id="P1",
        rights_basis=RightsBasis.OWNER_SUBMITTED,
        transaction_type="SALE",
        property_type="APARTMENT",
        city="Tehran",
        locality="District 1",
        geo_cell="geo:123",
        price_minor=12_345_678,
        area_sqm=95.5,
        bedrooms=2,
        title="Apartment",
        description="Detailed property description",
        image_hashes=("img-a", "img-b", "img-c"),
        source_updated_at=NOW - timedelta(minutes=5),
        last_verified_at=NOW,
        state=ListingState.ACTIVE,
    )


class Phase10LocalizationTests(unittest.TestCase):
    def test_persian_and_english_profiles_preserve_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            try:
                canonical = inventory.add_source(candidate())
                presentation = RealEstatePresentationService(inventory)
                detail = presentation.consumer_listing(canonical, now=NOW)
                discovery = RealEstateDiscoveryService(inventory, public_base_url="https://example.test")
                doc = discovery.listing_document(canonical, now=NOW)

                fa = RealEstateMarketAdapter(
                    LocaleContext("fa-IR", "fa", "arabext", TextDirection.RTL, "Asia/Tehran", "IRR")
                ).localize_consumer_listing(detail, canonical_url=doc.canonical_url)
                en = RealEstateMarketAdapter(
                    LocaleContext("en-US", "en", "latn", TextDirection.LTR, "UTC", "USD")
                ).localize_consumer_listing(detail, canonical_url=doc.canonical_url)

                self.assertEqual(fa.direction, TextDirection.RTL)
                self.assertEqual(en.direction, TextDirection.LTR)
                self.assertIn("۱۲٬۳۴۵٬۶۷۸", fa.price_text)
                self.assertIn("$12,345,678", en.price_text)
                self.assertIn("۱۵:۳۰", fa.last_verified_text)
                self.assertIn("12:00", en.last_verified_text)

                # Locale is representation only: protected semantics remain identical.
                for field in ("canonical_id", "canonical_url", "state", "trust_code", "verification_badge", "message_codes"):
                    self.assertEqual(getattr(fa, field), getattr(en, field))
                self.assertEqual(detail.price_minor, 12_345_678)
                self.assertEqual(detail.area_sqm, 95.5)
            finally:
                inventory.close()

    def test_unknown_message_code_falls_back_observably(self) -> None:
        adapter = RealEstateMarketAdapter(
            LocaleContext("en-US", "en", "latn", TextDirection.LTR, "UTC", "EUR")
        )
        message = adapter.localize_message("FUTURE_UNKNOWN_CODE")
        self.assertTrue(message.fallback_used)
        self.assertEqual(message.text, "[FUTURE_UNKNOWN_CODE]")
        self.assertEqual(message.code, "FUTURE_UNKNOWN_CODE")

    def test_currency_must_be_explicit_and_is_not_inferred_from_locale(self) -> None:
        eur_in_persian = RealEstateMarketAdapter(
            LocaleContext("fa-IR", "fa", "arabext", TextDirection.RTL, "Asia/Tehran", "EUR")
        )
        self.assertEqual(eur_in_persian.format_amount(1234), "۱٬۲۳۴ یورو")
        with self.assertRaises(ValueError):
            RealEstateMarketAdapter(
                LocaleContext("fa-IR", "fa", "arabext", TextDirection.RTL, "Asia/Tehran", "")
            )

    def test_naive_datetime_is_rejected_and_timezone_is_explicit(self) -> None:
        adapter = RealEstateMarketAdapter(
            LocaleContext("en-US", "en", "latn", TextDirection.LTR, "Europe/Berlin", "EUR")
        )
        with self.assertRaises(ValueError):
            adapter.format_datetime(datetime(2026, 8, 25, 12, 0))
        rendered = adapter.format_datetime(NOW)
        self.assertIn("14:00", rendered)

    def test_locale_profile_cannot_mix_rtl_and_ltr_semantics(self) -> None:
        with self.assertRaises(ValueError):
            RealEstateMarketAdapter(
                LocaleContext("fa-IR", "fa", "arabext", TextDirection.LTR, "Asia/Tehran", "IRR")
            )
        with self.assertRaises(ValueError):
            RealEstateMarketAdapter(
                LocaleContext("en-US", "en", "latn", TextDirection.LTR, "Not/AZone", "USD")
            )

    def test_locale_schema_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schemas/real-estate-locale-context.schema.json").read_text())
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["direction"]["enum"], ["RTL", "LTR"])
        self.assertIn("currency_code", schema["required"])


if __name__ == "__main__":
    unittest.main()
