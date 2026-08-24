# ADR-0001 — Hybrid Deterministic Control Plane with Bounded AI Workers

**Status:** Accepted  
**Date:** 2026-08-25

## Context

AI Factory needs enough autonomy to convert broad product missions into implemented, tested software, while remaining reliable, inspectable, secure and model-independent.

A pure free-form multi-agent swarm is attractive for demos but creates problems in production:

- opaque coordination,
- correlated hallucinations,
- unbounded loops/cost,
- difficult replay/debugging,
- unclear authority,
- memory contamination,
- unsafe retries,
- weak permission boundaries.

A fully deterministic workflow, however, cannot perform the open-ended reasoning and design work for which LLM agents are valuable.

## Decision

Use a **hybrid architecture**.

### Deterministic Control Plane owns

- mission/run identity,
- task state machine,
- dependency graph state,
- policy/permission decisions,
- budgets and limits,
- artifact/version registry,
- approval state,
- retry/idempotency metadata,
- event/audit ledger,
- final state transitions.

### AI workers own

- interpretation,
- planning proposals,
- product reasoning,
- architecture proposals,
- UX design,
- code generation/refactoring,
- test generation,
- review/critique,
- research and synthesis.

Workers produce proposals/artifacts/evidence. They do not directly redefine policy or canonical state semantics.

## Orchestration strategy

The Factory supports two execution modes.

### Single-worker fast path
Use when one bounded worker can satisfy the task and independent specialization would not improve quality enough to justify overhead.

### Multi-agent / Pod path
Use when one or more are true:

- distinct professional expertise is required,
- work can safely run in parallel,
- independent review is required,
- contexts should be isolated,
- adversarial verification adds value,
- mission size exceeds one worker's practical context.

Multi-agent is a routing decision, not a default requirement.

## Communication

Internal canonical communication uses typed objects and versioned artifacts, not direct free-form chat as the source of truth.

The runtime may support conversational deliberation internally, but only structured outputs can trigger task/state transitions.

## Shared state

Use:

- append-audited event history,
- versioned canonical artifacts,
- materialized projections for current state,
- isolated scratch contexts per worker.

Do not use one globally mutable LLM memory blob.

## External interoperability

The internal protocol remains Factory-owned.

Adapters may support:

- MCP for tools/context providers,
- A2A for external/remote agent interoperability,
- provider-specific agent SDKs.

No external framework or protocol becomes the canonical domain model.

## Consequences

### Positive

- easier testing and replay,
- clear authority boundaries,
- model/provider replaceability,
- safer retries and approvals,
- lower risk of swarm chaos,
- single-agent efficiency remains available,
- better observability and debugging.

### Negative

- more runtime engineering than a prompt-only swarm,
- schemas/policies must be maintained,
- some AI flexibility is intentionally constrained,
- durable state and artifact versioning add implementation work.

These costs are accepted because the goal is a reusable software factory, not an agent demo.

## Deferred decisions

The following remain open until implementation benchmarks exist:

- exact durable workflow engine,
- primary LLM provider/model router,
- database/storage technology,
- queue implementation,
- sandbox provider,
- degree of A2A/MCP adoption,
- model diversity policy for critical reviews.

## Evaluation criterion

ADR-0001 remains valid unless experiments show another architecture produces better reliability, security and cost under equivalent mission workloads. Architecture is evidence-driven and may be superseded by a new ADR.
