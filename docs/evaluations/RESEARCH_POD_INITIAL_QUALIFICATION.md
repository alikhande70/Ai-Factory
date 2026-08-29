# Research Pod — Initial Qualification

**Status:** PASS for initial bounded evidence-verification capability  
**Qualified code head:** `ff6a72f7c7049d831e4e258d58e4bc79f270b5aa`  
**GitHub Actions run:** `33276397326` — `success`  
**Test file:** `tests/test_research_pod.py`

## What was qualified

The initial Research Pod implementation demonstrates a deterministic evidence boundary around probabilistic research workers.

The qualification verifies:

1. typed research questions, sources, claims, evidence links and bundles,
2. exact source provenance with URI, publisher, retrieval timestamp, content fingerprint and independence group,
3. stable bundle fingerprints,
4. critical-claim evidence requirements,
5. source-independence checks that reject mirrored/copied evidence as fake corroboration,
6. high-authority evidence requirements for critical claims,
7. contradiction preservation,
8. freshness-window enforcement,
9. observable handling of insufficient evidence,
10. multi-role participation metadata without treating role count as proof of independence.

## Controlled Phase 10-H research fixture

The first positive fixture uses standards/runtime evidence relevant to the current real-estate localization milestone:

- Unicode CLDR Persian number formatting,
- W3C language/direction metadata guidance,
- RFC 5646 / BCP 47 language tags,
- Python `zoneinfo` / IANA timezone support.

The fixture passes only because each claim is source-traced and the critical standards claims have authoritative primary evidence.

## Negative tests

The suite deliberately attempts to pass weak research and confirms rejection when:

- two URLs are actually one independent source group,
- a supported claim hides contradictory evidence,
- a freshness-bounded conclusion relies only on stale evidence,
- a critical claim has no high-authority support.

An insufficient-evidence claim may remain in an accepted low-impact bundle only when it stays visibly insufficient; an overconfident insufficient claim is surfaced as an issue rather than silently upgraded to fact.

## What this PASS does not mean

This qualification does **not** prove that web-search workers always find the right sources, that language models cannot misread a source, or that Research Pod output is automatically trusted organizational memory.

Research discovery remains probabilistic. Promotion of research findings into canonical state or organizational memory still crosses the Factory's normal policy, review and provenance gates.

## Next research-driven engineering work

Phase 10-H research identified three material implementation follow-ups:

1. string-level language/direction metadata for mixed-direction user content,
2. explicit canonical money/minor-unit semantics,
3. cross-platform timezone-data capability checks.

See `docs/research/PHASE10H_LOCALIZATION_RESEARCH.md`.
