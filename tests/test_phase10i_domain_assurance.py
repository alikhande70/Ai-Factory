from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from missions.real_estate import (
    DuplicatePriceDivergenceDetector,
    ListingCandidate,
    ListingState,
    LocaleContext,
    RealEstateMarketAdapter,
    RealEstatePresentationService,
    RealEstateSearchService,
    RightsBasis,
    SQLiteInventoryStore,
    SQLiteTrustReviewStore,
    SearchQuery,
    TextDirection,
    TrustPresentation,
    TrustReviewCoordinator,
)
from missions.real_estate.discovery import RealEstateDiscoveryService


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def listing(
    *,
    listing_id: str,
    source_ref: str,
    publisher_id: str,
    price_minor: int,
    rights_basis: RightsBasis = RightsBasis.OWNER_SUBMITTED,
    verified_at: datetime = NOW,
) -> ListingCandidate:
    return ListingCandidate(
        listing_id=listing_id,
        source_ref=source_ref,
        publisher_id=publisher_id,
        rights_basis=rights_basis,
        transaction_type="SALE",
        property_type="APARTMENT",
        city="Tehran",
        locality="District 1",
        geo_cell="IR-THR-D1-A",
        price_minor=price_minor,
        area_sqm=100.0,
        bedrooms=2,
        title="Two bedroom apartment",
        description="Detailed property description with reviewed disclosures.",
        image_hashes=("shared-image", "img-b", "img-c"),
        source_updated_at=verified_at - timedelta(minutes=10),
        last_verified_at=verified_at,
        state=ListingState.ACTIVE,
    )


class Phase10IDomainAssuranceTests(unittest.TestCase):
    def test_bounded_full_stack_domain_invariants_hold_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = SQLiteInventoryStore(f"{directory}/inventory.db")
            reviews = SQLiteTrustReviewStore(f"{directory}/reviews.db")
            try:
                with self.assertRaises(PermissionError):
                    inventory.add_source(
                        listing(
                            listing_id="BAD",
                            source_ref="scrape://bad",
                            publisher_id="BAD-PUB",
                            price_minor=100_000_000,
                            rights_basis=RightsBasis.UNAUTHORIZED_SCRAPE,
                        )
                    )

                canonical = inventory.add_source(
                    listing(
                        listing_id="L1",
                        source_ref="owner://1",
                        publisher_id="P1",
                        price_minor=100_000_000,
                    )
                )
                self.assertEqual(
                    canonical,
                    inventory.add_source(
                        listing(
                            listing_id="L2",
                            source_ref="partner://2",
                            publisher_id="P2",
                            price_minor=160_000_000,
                            rights_basis=RightsBasis.PARTNER_FEED,
                        )
                    ),
                )

                search = RealEstateSearchService(inventory)
                page = search.search(SearchQuery(city="Tehran"), now=NOW)
                self.assertEqual(len(page.results), 1)
                self.assertEqual(page.results[0].canonical_id, canonical)

                detector = DuplicatePriceDivergenceDetector()
                coordinator = TrustReviewCoordinator(inventory, reviews, detector)
                case = coordinator.detect_and_queue(canonical)
                self.assertIsNotNone(case)

                presentation = RealEstatePresentationService(
                    inventory,
                    review_store=reviews,
                    detector=detector,
                )
                consumer = presentation.consumer_listing(canonical, now=NOW)
                self.assertEqual(consumer.trust_code, TrustPresentation.NEEDS_REVIEW)
                self.assertFalse(consumer.verification_badge)
                self.assertFalse(any("FRAUD" in code for code in consumer.message_codes))

                discovery = RealEstateDiscoveryService(
                    inventory,
                    public_base_url="https://example.test",
                )
                document = discovery.listing_document(canonical, now=NOW)
                self.assertTrue(document.indexable)

                fa_adapter = RealEstateMarketAdapter(
                    LocaleContext("fa-IR", "fa", "arabext", TextDirection.RTL, "Asia/Tehran", "IRR")
                )
                en_adapter = RealEstateMarketAdapter(
                    LocaleContext("en-US", "en", "latn", TextDirection.LTR, "UTC", "IRR")
                )
                fa = fa_adapter.localize_consumer_listing(
                    consumer,
                    canonical_currency_code="IRR",
                    canonical_url=document.canonical_url,
                )
                en = en_adapter.localize_consumer_listing(
                    consumer,
                    canonical_currency_code="IRR",
                    canonical_url=document.canonical_url,
                )
                for field in (
                    "canonical_id",
                    "canonical_url",
                    "currency_code",
                    "state",
                    "trust_code",
                    "verification_badge",
                    "message_codes",
                ):
                    self.assertEqual(getattr(fa, field), getattr(en, field))

                fa_doc = fa_adapter.localize_discovery_document(document)
                en_doc = en_adapter.localize_discovery_document(document)
                self.assertEqual(fa_doc.canonical_url, en_doc.canonical_url)
                self.assertEqual(fa_doc.route_path, en_doc.route_path)
                self.assertEqual(fa_doc.indexable, en_doc.indexable)
                self.assertEqual(fa_doc.robots_directive, en_doc.robots_directive)
                self.assertEqual(fa_doc.structured_data, en_doc.structured_data)

                # Stale canonical inventory must disappear from search/discovery rather
                # than being revived by presentation/localization layers.
                stale_canonical = inventory.add_source(
                    listing(
                        listing_id="STALE",
                        source_ref="owner://stale",
                        publisher_id="P3",
                        price_minor=90_000_000,
                        verified_at=NOW - timedelta(days=31),
                    )
                )
                stale_page = search.search(SearchQuery(city="Tehran"), now=NOW)
                self.assertNotIn(stale_canonical, {result.canonical_id for result in stale_page.results})
                stale_doc = discovery.listing_document(stale_canonical, now=NOW)
                self.assertFalse(stale_doc.indexable)
            finally:
                reviews.close()
                inventory.close()


if __name__ == "__main__":
    unittest.main()
