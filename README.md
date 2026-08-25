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

AI Factory deliberately avoids a free-form agent swarm. The architecture combines:

- deterministic canonical mission/task state, permissions, budgets, approvals, artifact versions and audit history,
- probabilistic AI workers for reasoning, planning, architecture, implementation and critique,
- typed Task / Artifact / Evidence / Review / Decision / Objection / Event / Escalation contracts,
- versioned canonical state separated from disposable worker scratch context,
- reviewed organizational memory with provenance and anti-poisoning controls,
- least-privilege and capability-scoped tool access,
- independent verification and protected evaluation baselines,
- explicit budgets, retry/reconciliation and durable-recovery semantics,
- human approval gates for consequential protected actions,
- a single-worker fast path when multi-agent coordination adds no measurable value,
- mission-specific Pods when specialization is justified,
- protocol/provider independence: MCP, A2A and provider SDKs remain boundary adapters rather than authority sources.

The 12 core agents are **organizational roles**, not a requirement to run 12 models for every task.

## Current implementation status

### Reusable Factory core

Phases 0–9 are qualified, covering project constitution, Control Plane/Orchestrator, durable runtime, Design Pod, Engineering Pod, Assurance Pod, reliability, interoperability, organizational memory/evaluation protection and a controlled qualification against a simpler baseline.

### Mission 001 — Real Estate Intelligence Platform

The bounded Mission 001 qualification is complete through Phase 10-I, including rights/provenance, inventory integrity and persistence, duplicate handling, search/geo, saved-search alerts, anomaly-review evidence, safe presentation, SEO/discovery, localization invariance and domain assurance.

No production deployment is implied by that qualification.

### Phase 11 — Production Hardening

The current code-side hardening state is:

**`CODE_QUALIFIED` — not `PRODUCTION_READY`.**

Qualified code-side controls include:

- multi-mission runtime isolation,
- verified SQLite backup/restore,
- scoped secret-reference handling and persistence redaction,
- non-destructive verifiable audit archival,
- durable incident-response state machine,
- deterministic dependency/SBOM inventory and exact-SHA CI action pinning,
- deterministic SLO evidence/claim boundaries,
- representative CI performance regression qualification,
- a final release-readiness gate that cannot convert missing external evidence into production readiness.

Current machine-readable state: [`evals/phase11/readiness_current.json`](evals/phase11/readiness_current.json).

Current evidence summary: [`docs/evaluations/PHASE11_CODE_QUALIFIED.md`](docs/evaluations/PHASE11_CODE_QUALIFIED.md) and [`docs/evaluations/PHASE11_PROGRESS.md`](docs/evaluations/PHASE11_PROGRESS.md).

### Verified external blockers

Production readiness is intentionally blocked because:

- GitHub `main` is currently **not branch protected**,
- a live production secret provider has not been connected/qualified,
- off-site recovery and measured RPO/RTO are not qualified,
- production SLO evidence does not exist.

Local/CI evidence is never promoted to a production claim merely because it passes.

## Competitive qualification track

AI Factory must not claim superiority over Hermes Agent, OpenHands, LangGraph, Microsoft Agent Framework, CrewAI or another system from architecture opinions alone.

See:

- [`docs/evaluations/COMPETITIVE_BENCHMARK_PLAN.md`](docs/evaluations/COMPETITIVE_BENCHMARK_PLAN.md)
- [`evals/competitive/benchmark_manifest.json`](evals/competitive/benchmark_manifest.json)

External comparison requires fixed cases, protected scoring, version/model/tool/budget pinning and preserved failures for all systems.

## Repository governance

Repository protection is a real remaining production blocker, not a documentation checkbox. The current GitHub branch state has been verified as unprotected.

See [`docs/governance/REPOSITORY_HARDENING.md`](docs/governance/REPOSITORY_HARDENING.md).

## Start here

A new human or language model should read:

1. [`README.md`](README.md)
2. [`ROADMAP.md`](ROADMAP.md) for architecture and phase structure
3. [`docs/evaluations/PHASE11_PROGRESS.md`](docs/evaluations/PHASE11_PROGRESS.md) for current hardening evidence
4. [`docs/evaluations/PHASE11_CODE_QUALIFIED.md`](docs/evaluations/PHASE11_CODE_QUALIFIED.md) for current release-readiness verdict
5. [`docs/foundation/FINAL_ARCHITECTURE_AUDIT.md`](docs/foundation/FINAL_ARCHITECTURE_AUDIT.md)
6. [`docs/foundation/MANIFESTO.md`](docs/foundation/MANIFESTO.md)
7. [`docs/foundation/GOVERNANCE.md`](docs/foundation/GOVERNANCE.md)
8. [`docs/foundation/THREAT_MODEL.md`](docs/foundation/THREAT_MODEL.md)
9. [`docs/agents/orchestrator.md`](docs/agents/orchestrator.md)
10. [`docs/evaluations/COMPETITIVE_BENCHMARK_PLAN.md`](docs/evaluations/COMPETITIVE_BENCHMARK_PLAN.md)

## Core rule for future models

Do not jump directly into building a requested app before reading repository state. AI Factory itself is the reusable product; individual apps are missions executed by it.

Never claim an external action, deployment, test, benchmark win, production SLO or readiness state unless exact evidence exists for it.
