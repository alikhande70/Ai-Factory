# Research Pod — Evidence-First Research Agents

**Status:** Initial qualified reusable capability  
**Purpose:** Give AI Factory a bounded research team that can investigate external facts, standards, competitors and mission-specific questions without allowing raw research output to become canonical truth automatically.

## Design objective

The Research Pod follows the Factory DNA:

> **Independent minds. Shared reality. Bounded authority. Verified action.**

Research agents are independent in reasoning, but their authority is narrow. They may discover, compare, challenge and synthesize evidence. They may **not** grant permissions, change governance, mutate protected canonical state, weaken tests, or promote their own conclusions directly into organizational memory.

## Roles

### R01 — Research Planner
- Converts a mission question into explicit sub-questions.
- Defines freshness windows and criticality.
- Identifies what kind of evidence would falsify the working hypothesis.
- Avoids creating unnecessary parallel research branches.

### R02 — Source Scout
- Finds primary standards, official documentation, papers and secondary/community evidence.
- Records exact source URI, publisher, retrieval time, publication time when known, content fingerprint and independence group.
- Does not decide that a source is true merely because it is popular or repeated elsewhere.

### R03 — Evidence Verifier
- Maps claims to explicit evidence links.
- Checks whether sources actually support the claim being made.
- Applies freshness and authority requirements.
- Rejects unsupported completion claims.

### R04 — Contradiction Analyst
- Searches for counter-evidence and incompatible interpretations.
- Prevents a supported conclusion from hiding known contradictory evidence.
- Marks claims `CONTESTED` when both sides remain materially supported.

### R05 — Research Synthesizer
- Produces the smallest decision-useful synthesis from verified claims.
- Preserves unresolved gaps and confidence limits.
- Cannot promote a finding into trusted organizational memory without the normal memory-review path.

### R06 — Research Red Team (activated for high-impact research)
- Attacks source independence, evidence coverage, freshness assumptions and hidden benchmark bias.
- Attempts to show that a research conclusion would change if one weak source disappeared.

R06 is not required for routine low-impact research.

## Communication model

Agents do not build truth through unbounded group chat. They exchange typed artifacts:

```text
ResearchQuestion
  -> SourceRecord[]
  -> ResearchClaim[] + EvidenceLink[]
  -> contradiction pass
  -> ResearchBundle
  -> deterministic ResearchVerifier
  -> candidate decision input
```

Worker scratch reasoning is not canonical state.

## Source hierarchy

The verifier records source class rather than treating every link equally:

1. `PRIMARY_STANDARD`
2. `OFFICIAL_DOCUMENTATION`
3. `PEER_REVIEWED`
4. `PREPRINT`
5. `VENDOR_DOCUMENTATION`
6. `SECONDARY`
7. `COMMUNITY`

This is not a universal truth ranking. A primary standard can define protocol behavior but cannot prove an unrelated empirical market claim. Source class is context, not proof by itself.

## Independence rule

Two URLs are not automatically two independent sources.

Mirrors, copied press releases, syndicated articles, summaries of the same paper and multiple pages owned by the same authority can share one `independent_group`.

For a critical claim, the default rule requires either:

- two independent supporting groups, or
- a normative primary standard when one authoritative specification is the actual source of truth for that narrow standards claim.

## Contradiction rule

A claim cannot remain `SUPPORTED` when its own evidence set contains material `CONTRADICTS` links. It must be downgraded/reframed or marked `CONTESTED`.

This prevents the common failure mode where a synthesizer cherry-picks the preferred side after a broad search.

## Freshness rule

Time-sensitive questions carry a `freshness_days` window. A supported claim must include supporting evidence observed or published inside that window.

Evergreen standards questions can omit the window.

## Research and memory boundary

Research results are **candidate knowledge**, not organizational memory.

Promotion into reusable memory still requires:

- provenance,
- review,
- evidence integrity,
- source integrity,
- normal memory lifecycle rules.

Raw web/tool output never writes directly to trusted long-term memory.

## Initial qualification

The first controlled qualification uses Phase 10-H localization research and verifies that the Research Pod can:

- preserve four high-authority source records,
- support Persian `arabext` numbering from Unicode CLDR,
- support explicit language/direction metadata from W3C guidance,
- support BCP 47 language identification from RFC 5646,
- support explicit IANA timezone handling through Python `zoneinfo`,
- reject fake source independence,
- reject hidden contradictions,
- reject stale evidence for freshness-bounded questions,
- keep insufficient evidence visibly insufficient.

Executable evidence: `tests/test_research_pod.py`.
