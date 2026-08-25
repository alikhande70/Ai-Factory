# Phase 10 — Mission 001 Progress

**Mission:** Real Estate Intelligence Platform  
**Current milestone:** 10-A — Inventory Integrity Foundation  
**Status:** IN PROGRESS / first executable slice qualified  
**Qualified head:** `571c4819bcecd904adc413f1409f0f542569dd9f`  
**GitHub Actions run:** `32844576057` — success

## What is now executable

The first Mission 001 domain pack lives outside the reusable Factory core under `missions/real_estate/`.

Implemented:

- explicit `RightsBasis` with owner-submitted, partner-feed, licensed-data and rejected unauthorized-scrape classes;
- typed `ListingCandidate` with source/publisher provenance;
- deterministic listing lifecycle and allowed transition map;
- deterministic freshness/expiry score using timezone-aware verification timestamps;
- deterministic disclosure/completeness score;
- duplicate fingerprint that deliberately ignores publisher/source identity while retaining stable property signals;
- deterministic baseline ranking with bounded explainable signals;
- rank ineligibility for expired/inactive or freshness-zero inventory.

## Verification evidence

`tests/test_phase10_real_estate_integrity.py` covers:

1. unauthorized scrape rejection;
2. fail-closed invalid lifecycle transition;
3. deterministic freshness expiry;
4. duplicate grouping across different publishers;
5. lower completeness for sparse inventory;
6. rank suppression for expired and stale inventory;
7. bounded/explainable ranking output;
8. rejection of out-of-range ranking signals.

The first version of the stale-listing fixture exposed a chronology defect in the test data (`last_verified_at` predating a newer `source_updated_at`). The failing CI run was not ignored: the fixture chronology was corrected so the stale case models a genuinely old source update followed by its last verification.

The corrected head `571c4819bcecd904adc413f1409f0f542569dd9f` completed GitHub Actions run `32844576057` successfully, including the repository-wide unit/orchestration suite.

## Architecture boundary preserved

Mission-specific code is isolated in `missions/real_estate/`. It imports no permission, state-transition or approval authority into the reusable Factory core. Production publishing, identity, billing and destructive/irreversible external actions remain governed by the existing Control Plane and human/policy gates.

## Research-backed design notes

The domain foundation intentionally treats freshness, provenance, duplicate handling, disclosure completeness and ranking as first-class data concerns rather than later moderation patches. The mission charter also prohibits unauthorized copying/republication of third-party listings.

## Next slice — 10-B

Build a persisted canonical inventory service with:

- immutable source records + canonical listing projection;
- source-to-canonical duplicate-group membership;
- freshness sweeper that expires rather than deletes;
- append-audited lifecycle history;
- publisher trust evidence contract (no model-confidence badges);
- query/filter contract for transaction/property/location/price attributes;
- restart/recovery tests;
- migration tests for the Mission 001 inventory schema.

10-B must preserve source history and avoid destructive merge semantics.
