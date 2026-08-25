# Mission 001 — Search & Geo Contract

**Status:** Phase 10-C deterministic baseline  
**Authority:** Domain search contract only; does not override Factory governance, listing rights, lifecycle, trust, approval or reliability rules.

## Purpose

Provide a deterministic, inspectable search boundary over the canonical real-estate inventory before any opaque ML ranking is considered.

Search operates on **canonical listings**, never raw source records, so duplicate source records do not create duplicate consumer results.

## Query contract

Canonical machine-readable schema: `schemas/real-estate-search.schema.json`.

Supported filters:

- free-text search,
- transaction type,
- property type,
- city,
- locality,
- geo-cell prefix,
- minimum/maximum price,
- bedrooms,
- listing states,
- exact radius query when all of `center_latitude`, `center_longitude` and `radius_km` are supplied,
- bounded page size,
- opaque query-bound cursor.

A radius query requires a configured `SQLiteGeoIndex`. Missing spatial infrastructure is an explicit runtime error; the system must not silently degrade an exact-radius request into a coarse locality filter.

## Geo semantics

`geo_cell_prefix` is a deterministic coarse filter.

Exact radius uses:

1. a latitude/longitude bounding-box pre-filter,
2. exact Haversine distance refinement,
3. deterministic distance calculation in kilometres.

The separate geo index is intentionally not authoritative for listing lifecycle, rights, provenance or publisher trust. It maps canonical listing IDs to coordinates and may later be replaced by a production spatial database without changing the canonical inventory contract.

## Ranking semantics

The baseline ranking reuses `SearchSignals` and `rank_listing()`.

Positive signals:

- text relevance,
- freshness,
- disclosure/completeness,
- verified publisher trust.

An unknown publisher receives trust score `0.0`; trust is never invented from model confidence or listing prose.

Listings that are inactive or freshness-expired are not eligible for ranking.

Text relevance is currently deterministic token matching:

- title match: weight `1.0`,
- city/locality match: weight `0.8`,
- description match: weight `0.5`.

This algorithm is deliberately simple and inspectable. Any future learned ranking system must beat the protected deterministic fixture without weakening its evaluator.

## Ordering and pagination

Sort order:

1. score descending,
2. verification time descending,
3. canonical ID ascending.

The canonical ID is the deterministic final tie-breaker.

Cursor payloads are opaque to clients and bound to a normalized query signature. Reusing a cursor with a materially different query is rejected rather than producing undefined pagination.

## Protected evaluation

`evals/real_estate/search_relevance_fixture.json` is the Phase 10-C protected deterministic relevance baseline.

`tests/test_phase10_search_qualification.py` qualifies:

- fixture ordering,
- controlled synthetic search latency on a 500-listing local SQLite inventory.

The synthetic latency guard is a regression baseline, **not a production SLO**.

Additional search/geo tests verify:

- canonical duplicate collapse,
- coarse geo-cell filtering,
- exact radius filtering,
- geo migration/restart behavior,
- query-bound cursors,
- equal-score/equal-time pagination tie-breaking,
- stale listing suppression,
- unknown-publisher trust behavior.

## Deferred

Phase 10-C does not claim:

- production-scale spatial indexing,
- multilingual semantic retrieval,
- personalized ranking,
- ML relevance,
- external search-engine deployment,
- production SLOs.

Those require separate evaluation, security and production-hardening gates.
