# Mission 001 — Saved Search & Alert Contract

**Status:** Phase 10-D deterministic baseline  
**Authority:** Internal domain event generation only. This contract does not authorize email, SMS, push, messaging, billing, account actions or any other external side effect.

## Purpose

Persist user-defined real-estate searches and deterministically detect canonical listings that become newly eligible for those searches after the saved search has established its baseline.

## Core semantics

A saved search contains:

- stable saved-search ID,
- owner ID,
- human-readable name,
- structured `SearchQuery`,
- enabled/disabled state,
- version.

Pagination cursors are explicitly forbidden from persisted saved searches. They are execution state, not product intent.

Machine-readable schema: `schemas/real-estate-saved-search.schema.json`.

## Baseline rule

The first evaluation of a new or materially edited saved search establishes a baseline of all listings that already match **without producing alert events**.

This prevents a newly created or edited search from generating an alert storm for inventory that already existed before monitoring began.

Only a canonical listing that qualifies after the baseline is eligible to create an internal alert event.

## Query-version isolation

A material query change increments the saved-search version and resets the baseline state.

Match identity is:

```text
saved_search_id + saved_search_version + canonical_id
```

This is intentional. Seen-state from an older query version must not poison a newer query version. Old match/outbox history remains preserved instead of being destructively rewritten.

## Idempotency and replay

For one query version, the same canonical listing can create at most one alert event.

Repeated evaluation and process restart must not create duplicate events. The match ledger and outbox are durable SQLite state with unique constraints enforcing the invariant.

The evaluator follows all search pages rather than assuming the first page contains every match.

## Lifecycle/freshness inheritance

Saved-search evaluation uses `RealEstateSearchService`, so alert eligibility inherits the deterministic search rules:

- stale/inactive listings are not rank eligible,
- canonical duplicates collapse,
- structured filters remain authoritative,
- unknown publisher trust is never invented,
- exact-radius behavior requires the configured geo index.

## External delivery boundary

`AlertEvent.status == PENDING_INTERNAL` means only that the Factory produced a durable internal event.

There is deliberately no method in the Phase 10-D domain component that sends email, SMS, push notifications or messages. Any future delivery adapter must cross the existing Factory Policy/Tool/Reliability boundary and, when applicable, the Human Approval boundary.

An internal alert event is therefore **not evidence that a user notification was delivered**.

## Qualification coverage

`tests/test_phase10_saved_search_alerts.py` verifies:

- initial baseline without alert storm,
- exactly-once internal event for a newly qualifying listing,
- replay idempotency,
- restart persistence,
- inactive/nonmatching suppression,
- query versioning and re-baselining,
- older seen-state cannot poison a newer query version,
- disabled-search behavior,
- persisted-cursor rejection,
- evaluation across more than one 100-result search page.

## Deferred

This baseline does not claim:

- production notification delivery,
- user contact-channel verification,
- notification scheduling/digests,
- per-channel retry/receipt semantics,
- unsubscribe/legal communication controls,
- production throughput/SLOs.

Those require separate policy, reliability, privacy and production-hardening work.
