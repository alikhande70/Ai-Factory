# AI Factory

AI Factory is an **AI-native software organization operating system**: a reusable system that turns a product mission into designed, implemented, tested and reviewable software through bounded specialist AI workers coordinated by a deterministic Control Plane.

> **Independent minds. Shared reality. Bounded authority. Verified action.**

## What this project is

AI Factory is not tied to one product such as real estate or e-commerce. Those products become **missions** executed by the Factory.

The long-term flow is:

```text
Human Mission
  → Product Definition
  → Architecture / UX
  → Dependency Graph
  → Specialist Execution
  → Evidence / Tests
  → Security + Red-Team Review
  → Integration
  → Release Candidate
  → Human Approval for protected actions
  → Deployment / Maintenance
```

## Architecture direction

The project deliberately avoids a free-form “agent swarm.”

The approved architecture combines:

- deterministic mission/task state machines,
- typed task/artifact/review protocols,
- versioned shared project state,
- replaceable specialist AI workers,
- least-privilege tool access,
- independent verification,
- explicit execution budgets,
- human approval gates for consequential actions,
- durable/replayable execution semantics,
- single-agent fast paths when multi-agent coordination adds no value,
- mission-specific Pods when extra specialization is justified.

The 12 initial agents are **organizational roles**, not a requirement to run 12 models for every task.

## Start here

A new human or language model should read these files in order:

1. [`ROADMAP.md`](ROADMAP.md) — source of truth for phases and current milestone.
2. [`docs/foundation/FINAL_ARCHITECTURE_AUDIT.md`](docs/foundation/FINAL_ARCHITECTURE_AUDIT.md) — final pre-build architecture audit.
3. [`docs/foundation/MANIFESTO.md`](docs/foundation/MANIFESTO.md) — company principles.
4. [`docs/foundation/COMPANY_DNA.md`](docs/foundation/COMPANY_DNA.md) — shared and role-specific behavior.
5. [`docs/foundation/GOVERNANCE.md`](docs/foundation/GOVERNANCE.md) — authority and approval model.
6. [`docs/foundation/AUTONOMY_MODEL.md`](docs/foundation/AUTONOMY_MODEL.md) — bounded autonomy levels.
7. [`docs/foundation/THREAT_MODEL.md`](docs/foundation/THREAT_MODEL.md) — initial agentic threat model.
8. [`docs/architecture/decisions/ADR-0001-hybrid-control-plane.md`](docs/architecture/decisions/ADR-0001-hybrid-control-plane.md) — accepted architecture decision.
9. [`docs/agents/orchestrator.md`](docs/agents/orchestrator.md) — A01 Orchestrator contract.

## Current status

**Foundation architecture is locked enough to begin Phase 1 implementation.**

Current work is focused on:

- formal task/mission/artifact schemas,
- deterministic state transitions,
- Orchestrator evaluation fixtures,
- mock execution before connecting real autonomous workers.

## Core rule for future models

Do not jump directly into building a requested app before reading the project state. AI Factory itself is the reusable product; individual apps are missions executed by it.

Do not claim an external action, deployment, test or verification happened unless there is evidence that it actually happened.
