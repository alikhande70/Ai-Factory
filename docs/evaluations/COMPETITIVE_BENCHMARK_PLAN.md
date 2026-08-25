# AI Factory — Competitive Benchmark Plan

**Status:** Protected evaluation design  
**Purpose:** Compare AI Factory against simpler and external agent systems using reproducible evidence rather than architecture claims.

## 1. Principle

AI Factory must not claim to be better than Hermes Agent, OpenHands, LangGraph-based systems, Microsoft Agent Framework, CrewAI or any other system without controlled benchmark evidence.

> Architecture quality is a hypothesis. Benchmark evidence decides whether it creates measurable value.

The benchmark is intentionally designed to make it possible for AI Factory to lose.

## 2. Required baselines

Every competitive run must include:

1. `SINGLE_WORKER_BASELINE` — one capable model/worker with the same mission and comparable tool access.
2. `AI_FACTORY` — the current qualified Factory release.

External systems may be added as reproducible adapters:

- `HERMES_AGENT`
- `OPENHANDS`
- `LANGGRAPH_REFERENCE`
- `MICROSOFT_AGENT_FRAMEWORK_REFERENCE`
- `CREWAI_REFERENCE`

External names identify benchmark targets, not bundled dependencies or endorsement.

## 3. Version pinning

A run is invalid unless it records:

- system name,
- exact version/tag/commit/container digest when available,
- model/provider/version,
- benchmark-case version,
- tool/runtime permissions,
- token/tool/time budget,
- environment fingerprint,
- evaluator version.

Do not compare a current AI Factory build against an unspecified moving target.

## 4. Fairness rules

- Use the same mission text and protected acceptance criteria.
- Equalize model class and budget where practical.
- If tool access differs materially, record the difference and classify the result as `NON_EQUIVALENT_TOOLS`.
- Do not give AI Factory hidden repository-specific hints unavailable to the baseline.
- Do not rewrite a case after observing a competitor failure.
- Do not discard failed AI Factory runs while keeping competitor failures.
- Separate warm-start and cold-start experiments.
- Separate architecture effectiveness from raw model capability.
- Record cost, latency and tool-call count in addition to correctness.

## 5. Benchmark dimensions

Each mission is scored on protected dimensions:

| Dimension | Meaning |
|---|---|
| Functional correctness | Acceptance criteria and executable behavior |
| Evidence coverage | Claims supported by tests/logs/artifacts |
| Security/governance | Protected boundaries respected |
| Recovery/replay | Interruption and retry behavior |
| Traceability | Requirement → task → artifact → evidence chain |
| Maintainability | Coherent structure and limited unnecessary complexity |
| Human intervention | Routine clarification/escalation burden |
| Cost | Tokens/model/tool/infrastructure consumption |
| Latency | Wall-clock completion time |
| Failure containment | Whether one failure poisons unrelated work |
| Provider portability | Whether behavior depends on one model/provider |

No single aggregate score may hide a critical security/governance failure.

## 6. Hard failure gates

A run cannot be declared a benchmark winner if it:

- claims unexecuted work as complete,
- bypasses a protected approval boundary,
- exposes or commits secrets,
- silently weakens its evaluator or acceptance criteria,
- performs unauthorized destructive/external actions,
- loses required provenance for critical artifacts,
- produces a critical security failure defined by the case.

These are `DISQUALIFIED`, not merely point deductions.

## 7. Case families

The benchmark suite should grow through versioned families:

### A. Small deterministic task
Purpose: prove the Factory does not over-orchestrate simple work.
Expected outcome: single-worker fast path should be competitive.

### B. Ambiguous product mission
Purpose: requirements, contradiction detection and scope discipline.

### C. Full-stack implementation
Purpose: product → architecture → implementation → integration → evidence.

### D. Adversarial security mission
Purpose: prompt injection, tool boundaries, secrets, authz and malicious retrieved content.

### E. Recovery mission
Purpose: crash/restart, duplicate side effects, retry/reconcile and stale state.

### F. Cross-role change
Purpose: upstream requirement change invalidates downstream architecture/code/tests correctly.

### G. Domain mission
Purpose: evaluate Mission Pod specialization without leaking domain authority into reusable Factory core.

## 8. Minimum initial suite

The first official competitive suite should contain at least 20 cases:

- 4 small/fast-path cases,
- 4 product/architecture cases,
- 4 implementation/integration cases,
- 3 security/adversarial cases,
- 3 recovery/reliability cases,
- 2 domain-specific cases.

Expand to 50+ only after the evaluator itself is stable.

## 9. Statistical discipline

Probabilistic systems require repeated runs.

For model-driven cases:

- recommended minimum: 5 runs per system/case for exploratory comparison,
- preferred: 10+ for publishable internal conclusions,
- record success rate, median and tail latency/cost,
- preserve all raw results,
- never report only the best run.

Deterministic checks may execute once per produced artifact, but generation variability still requires repeated end-to-end runs.

## 10. Evaluator independence

Critical scoring should prefer:

1. executable tests/static analysis,
2. deterministic contract validation,
3. environment/state inspection,
4. isolated reviewer models only for dimensions that cannot be objectively measured.

An evaluated worker may not modify:

- benchmark cases,
- expected critical invariants,
- evaluator code,
- scoring weights,
- disqualification rules.

Any benchmark change creates a new benchmark version.

## 11. Reporting

Every published comparison must clearly separate:

- `MEASURED` — observed in reproducible runs,
- `INFERRED` — engineering interpretation from evidence,
- `NOT_TESTED` — no valid evidence yet.

Required report fields:

- benchmark version,
- tested systems and versions,
- run count,
- model/provider configuration,
- tool/environment equivalence notes,
- per-dimension results,
- disqualifications,
- cost/latency,
- known limitations,
- raw result artifact locations.

## 12. Success criteria for AI Factory

The project succeeds only if the Factory demonstrates one or more measurable advantages that justify its orchestration overhead, such as:

- higher verified completion on complex missions,
- materially better security/governance compliance,
- superior recovery and traceability,
- lower human coordination burden,
- better maintainability or cross-role change handling.

If the single-worker baseline wins on simple tasks, that is expected and validates the fast-path design rather than counting as failure.

## 13. Current status

This document defines the benchmark governance only. No external competitive win is currently claimed from this file.

Official results require actual version-pinned runs and preserved raw evidence.
