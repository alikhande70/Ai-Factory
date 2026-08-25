# Mission 001 — Real Estate Intelligence Platform

**Status:** ACTIVE — Phase 10 foundation
**Mission ID:** `MISSION-001-REAL-ESTATE`
**Quality profile:** `PRODUCTION`

## Objective

Build a trustworthy real-estate discovery and intelligence platform that helps people find relevant, current property opportunities while giving legitimate publishers a structured, auditable way to supply inventory.

This mission is the first domain mission executed on top of the qualified AI Factory. Domain code must remain isolated from the reusable Factory core.

## Product thesis

A property portal is not merely listing CRUD plus filters. The hard product/engineering problems are inventory integrity, search relevance, geospatial discovery, freshness, duplicate resolution, disclosure quality, publisher trust and explainable ranking.

The first implementation therefore prioritizes **inventory truth before growth features**.

## Locked domain principles

1. **Rights-aware ingestion.** Inventory may enter canonical state only when its rights basis is explicitly recorded as owner-submitted, partner-feed, or licensed-data. Unauthorized scraping/republication is not an allowed source.
2. **Provenance first.** Every listing candidate carries source, publisher and ingestion provenance.
3. **Freshness is a state property.** A listing is not considered active merely because a row exists. Availability must be re-confirmable and automatically expire under policy.
4. **Duplicate-aware inventory.** Multiple source records may refer to the same underlying property; the system must preserve source records while enabling deterministic duplicate grouping.
5. **Search does not reward stale supply.** Inactive/expired inventory is not rank-eligible.
6. **Trust signals are evidence-backed.** A badge, score or verification claim may not be generated from model confidence alone.
7. **Completeness matters.** Sparse listings may exist as candidates but must not receive the same quality treatment as well-disclosed inventory.
8. **No hidden pay-to-trust coupling.** Paid visibility, if ever added, may not imply verification or safety.
9. **Locale is configuration, not architecture.** Currency, language, address conventions and legal disclosures are market-specific adapters.
10. **Protected actions remain protected.** Production publishing, identity verification, billing and irreversible account actions stay behind policy/human gates.

## Initial user outcomes

### Searcher
- Search by location, transaction type, property type, price and core attributes.
- See current inventory rather than stale inventory.
- Understand why a result is relevant.
- See freshness and disclosure-quality signals.
- Avoid obvious duplicate clutter.

### Publisher
- Submit inventory with structured fields and explicit rights basis.
- Update lifecycle state and availability.
- Re-confirm stale inventory without creating a new listing.
- Receive deterministic feedback on missing disclosure fields.

### Platform operator
- Trace every canonical listing to its source/provenance.
- Identify duplicate candidates.
- Expire inventory according to policy.
- Keep ranking deterministic and testable before adding ML personalization.
- Review suspicious/anomalous inventory without silently deleting audit history.

## Phase 10-A — Inventory Integrity Foundation

First executable milestone:

- typed property/listing domain contracts,
- explicit source-rights contract,
- deterministic listing lifecycle,
- freshness/expiry policy,
- completeness scoring,
- duplicate fingerprinting,
- deterministic rank eligibility and baseline ranking,
- tests proving unauthorized sources, invalid state transitions and stale ranking are rejected.

### Exit criteria

Phase 10-A is complete only when executable tests prove:

1. an unauthorized ingestion rights basis cannot become an accepted listing candidate;
2. invalid lifecycle transitions fail closed;
3. a listing becomes stale/expired under a deterministic age policy;
4. equivalent normalized candidates produce the same duplicate fingerprint;
5. expired/inactive listings are not rank eligible;
6. ranking uses bounded, inspectable signals rather than opaque model confidence;
7. domain code is isolated from reusable Factory control-plane code.

## Deferred work

Not part of 10-A:

- production crawling/scraping,
- payments,
- mortgage/financial products,
- automated legal advice,
- identity-document processing,
- production deployment,
- opaque ML ranking,
- cross-platform unauthorized listing republication.

These require later product, policy, legal, security and/or human approval work.

## Domain roles to activate as needed

- Real Estate Domain Specialist
- Search / Ranking Specialist
- Trust & Fraud Specialist
- Data Acquisition / Provenance Specialist
- SEO / Discovery Specialist
- Localization Specialist

These are mission-specific Pods, not permanent additions to the Factory core.
