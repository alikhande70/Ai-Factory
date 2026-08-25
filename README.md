# AI Factory

AI Factory is an **AI-native software organization operating system**: a reusable system that turns a product mission into designed, implemented, tested and reviewable software through bounded specialist AI workers coordinated by a deterministic Control Plane.

> **Independent minds. Shared reality. Bounded authority. Verified action.**

## What this project is

AI Factory is not tied to one product such as real estate or e-commerce. Those products are **missions** executed by the Factory.

The intended flow is:

```text
Human Mission
  → Product Definition
  → Architecture / UX
  → Dependency Graph
  → Specialist Engineering
  → Evidence / Tests
  → Security + QA + Red-Team Review
  → Reliability / Release Qualification
  → Human Approval for protected actions
  → Deployment / Maintenance
```

## Locked architecture

AI Factory deliberately avoids a free-form agent swarm. The current architecture combines:

- a deterministic Control Plane for canonical mission/task state, permissions, budgets, approvals, artifact versions and audit history,
- probabilistic AI workers for reasoning, planning, architecture, implementation and critique,
- typed Task / Artifact / Evidence / Review / Decision / Objection / Event / Escalation contracts,
- versioned canonical shared state separated from disposable worker scratch context,
- reviewed organizational memory with provenance and anti-poisoning controls,
- least-privilege and capability-scoped tool access,
- independent verification and protected evaluation baselines,
- explicit execution budgets, retry and reconciliation semantics,
- human approval gates for financial, identity-bound, destructive, secret-bearing and other protected actions,
- a single-worker fast path when multi-agent coordination does not add measurable value,
- mission-specific Pods when extra specialization is justified,
- protocol/provider independence: MCP, A2A and model SDKs remain boundary adapters rather than authority sources.

The 12 core agents are **organizational roles**, not a requirement to run 12 models for every task.

## Current implementation status

The reusable Factory foundation has passed Phases 0–9, including:

- project constitution and architecture audit,
- Control Plane and Orchestrator foundation,
- durable local runtime,
- Design Pod,
- Engineering Pod,
- Assurance Pod,
- reliability and durable execution semantics,
- interoperability boundaries,
- organizational memory and evaluation protection,
- a controlled Factory qualification mission against a simpler baseline.

The repository is now executing **Phase 10 — Mission 001: Real Estate Intelligence Platform**.

Current roadmap milestone: **Phase 10-H — Localization & Market Adapters**.

Completed Mission 001 slices already include canonical inventory integrity/persistence, search and geo, saved-search alerts, trust/anomaly review, safe consumer/publisher presentation contracts and SEO/discovery surfaces. See [`ROADMAP.md`](ROADMAP.md) for the authoritative current state and evidence links.

## Competitive qualification track

AI Factory must not claim superiority over Hermes Agent, OpenHands, LangGraph, Microsoft Agent Framework, CrewAI or any other system from architecture opinions alone.

A protected competitive benchmark track is defined in:

- [`docs/evaluations/COMPETITIVE_BENCHMARK_PLAN.md`](docs/evaluations/COMPETITIVE_BENCHMARK_PLAN.md)
- [`evals/competitive/benchmark_manifest.json`](evals/competitive/benchmark_manifest.json)

The benchmark uses fixed mission cases, protected scoring dimensions, equalized budgets where practical, version-pinned external systems, reproducible evidence and a mandatory single-worker baseline. Architecture claims and benchmark results must remain separate until external runs actually exist.

## Repository governance note

The software architecture is stricter than the repository governance currently enforced by GitHub settings. Branch protection, required checks and review policy must be treated as a production-hardening requirement rather than assumed to exist.

See [`docs/governance/REPOSITORY_HARDENING.md`](docs/governance/REPOSITORY_HARDENING.md).

## Start here

A new human or language model should read these files in order:

1. [`ROADMAP.md`](ROADMAP.md) — source of truth for phases and current milestone.
2. [`docs/foundation/FINAL_ARCHITECTURE_AUDIT.md`](docs/foundation/FINAL_ARCHITECTURE_AUDIT.md) — foundation architecture audit.
3. [`docs/foundation/MANIFESTO.md`](docs/foundation/MANIFESTO.md) — company principles.
4. [`docs/foundation/COMPANY_DNA.md`](docs/foundation/COMPANY_DNA.md) — shared and role-specific behavior.
5. [`docs/foundation/GOVERNANCE.md`](docs/foundation/GOVERNANCE.md) — authority and approval model.
6. [`docs/foundation/AUTONOMY_MODEL.md`](docs/foundation/AUTONOMY_MODEL.md) — bounded autonomy levels.
7. [`docs/foundation/THREAT_MODEL.md`](docs/foundation/THREAT_MODEL.md) — agentic threat model.
8. [`docs/architecture/decisions/ADR-0001-hybrid-control-plane.md`](docs/architecture/decisions/ADR-0001-hybrid-control-plane.md) — core architecture decision.
9. [`docs/agents/orchestrator.md`](docs/agents/orchestrator.md) — A01 Orchestrator contract.
10. [`docs/evaluations/COMPETITIVE_BENCHMARK_PLAN.md`](docs/evaluations/COMPETITIVE_BENCHMARK_PLAN.md) — evidence rules for external comparison.

## Core rule for future models

Do not jump directly into building a requested app before reading repository state. AI Factory itself is the reusable product; individual apps are missions executed by it.

Never claim an external action, deployment, test, benchmark win or verification occurred unless there is evidence that it actually occurred.
