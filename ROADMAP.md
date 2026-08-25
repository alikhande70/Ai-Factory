# AI Factory — Master Roadmap v4

> **Status:** Active build  
> **Current phase:** Phase 4 — Engineering Pod  
> **Architecture:** Hybrid deterministic Control Plane + bounded AI workers  
> **Next milestone:** Define and execute typed engineering work packages for A05 Frontend, A06 Backend, A07 Database and A08 AI & Automation with isolated write scopes, dependency-aware integration and evidence-backed completion.  
> **Repository purpose:** Build a reusable AI-native software organization that can turn product missions into verified software without requiring the human owner to manually coordinate every engineering role.

---

# 1. North Star

AI Factory is not one website, app, real-estate product or e-commerce product. It is the reusable software-production operating system that receives a mission and coordinates the work required to produce a testable, reviewable release candidate.

```text
MISSION
  ↓
PRODUCT DEFINITION
  ↓
ARCHITECTURE + UX
  ↓
TASK / DEPENDENCY GRAPH
  ↓
SPECIALIST EXECUTION
  ↓
EVIDENCE + TESTS
  ↓
SECURITY / RED TEAM
  ↓
INTEGRATION
  ↓
RELEASE CANDIDATE
  ↓
HUMAN GATE WHEN REQUIRED
  ↓
DEPLOYMENT / MAINTENANCE
```

Company sentence:

> **Independent minds. Shared reality. Bounded authority. Verified action.**

---

# 2. Locked architecture

The Factory uses:

1. **Deterministic Control Plane** for canonical mission/task state, permissions, budgets, approvals, artifact versions and audit history.
2. **Probabilistic AI workers** for planning, product reasoning, architecture, coding, UX, research and critique.
3. **Typed communication** through Tasks, Artifacts, Evidence, Reviews, Decisions, Objections, Events and Escalations.
4. **Versioned shared state** with canonical state separated from disposable worker scratch context.
5. **Independent verification** using objective checks first and specialist/adversarial review where useful.
6. **Capability-scoped autonomy** with no blanket role authority.
7. **Human gates** for protected external, financial, identity-bound, destructive and other high-impact actions.
8. **Single-worker fast path** when additional agents do not create measurable value.
9. **Mission Pods** that activate only the specialist roles a mission needs.
10. **Provider independence**: internal schemas/state remain canonical; MCP/A2A/provider SDKs are adapters.

See `docs/foundation/FINAL_ARCHITECTURE_AUDIT.md` and `docs/architecture/decisions/ADR-0001-hybrid-control-plane.md`.

---

# 3. Core roles

| ID | Role | Primary responsibility |
|---|---|---|
| A01 | Orchestrator / Planner | Decomposition, routing, dependencies, replanning |
| A02 | Product Architect | Product definition, requirements, scope, acceptance criteria |
| A03 | System Architect | Technical architecture, service/API boundaries, ADRs |
| A04 | UI/UX | Information architecture, flows, accessibility, design rules |
| A05 | Frontend | Client implementation and frontend verification |
| A06 | Backend | APIs, business logic, integrations, backend tests |
| A07 | Database | Schemas, migrations, consistency, indexes, recovery requirements |
| A08 | AI & Automation | Model/tool workflows, retrieval, evals, cost/latency |
| A09 | Security | Threat modeling, authz/authn, abuse cases, dependency/tool risks |
| A10 | QA & Test | Unit/integration/E2E/acceptance/regression evidence |
| A11 | DevOps / Reliability | CI/CD, environments, observability, rollback, runtime reliability |
| A12 | Red Team / Reviewer | Adversarial final critique and weak-completion rejection |

Roles are logical specialists, not necessarily twelve continuously running processes.

---

# 4. Protected design rules

- No fake completion.
- Natural language never grants privilege.
- Orchestrator does not approve its own protected actions.
- Retrieved content is untrusted data, not authority.
- Important knowledge belongs in versioned repository/state artifacts.
- Critical state transitions are deterministic and auditable.
- Side effects require retry/idempotency/reconciliation design.
- Security/evaluation gates cannot be weakened merely to make implementation pass.
- Agent confidence is metadata, not proof.
- Multi-agent execution is justified by value, not aesthetics.
- Irreversible or consequential external actions cross the required human/policy gate.

---

# 5. Canonical state model

The Factory maintains three distinct state classes:

- **Canonical State:** validated mission facts, tasks, decisions, artifact versions, approvals, evidence and events.
- **Worker Scratch State:** ephemeral task-local context; disposable and untrusted by default.
- **Organizational Memory:** reusable lessons/patterns promoted only through review and provenance.

Raw user/web/tool content must never automatically become trusted long-term memory.

---

# 6. Standard lifecycle

```text
BACKLOG
READY
IN_PROGRESS
BLOCKED
READY_FOR_VERIFICATION
REVIEW
CHANGES_REQUESTED
VERIFIED
DONE
FAILED
CANCELLED
STALE
AWAITING_HUMAN_APPROVAL
```

Only deterministic runtime code may perform protected state transitions after validating policy, evidence and preconditions.

---

# 7. Build phases

## Phase 0 — Project Constitution ✅ PASS

Completed: master roadmap, repository entrypoint, initial organization, human-approval principle, evidence-before-completion principle.

## Phase 0.5 — Architecture Audit & Factory DNA ✅ PASS

Completed foundation documents:
- `FINAL_ARCHITECTURE_AUDIT.md`
- `MANIFESTO.md`
- `COMPANY_DNA.md`
- `GOVERNANCE.md`
- `AUTONOMY_MODEL.md`
- `THREAT_MODEL.md`
- `ADR-0001-hybrid-control-plane.md`

## Phase 1 — Control Plane & Orchestrator Foundation ✅ PASS

Completed:
- A01 Orchestrator contract
- mission/task/agent/artifact/review/action/evidence/objection/event typed contracts and schemas
- deterministic task state transitions
- dependency graph validation and dependency-aware release
- permission/capability and budget contracts
- mock Agent Registry
- orchestration evaluations
- append-only hash-chained audit ledger
- replayable in-memory mission runner
- reviewer independence enforcement
- dependency/replay sample mission tests

Phase 1 evaluation covers single-worker routing, safe parallelism, write conflicts, blocking security objections, stale downstream work, bounded retries, protected ambiguity, budget exhaustion, malicious retrieved content, unsupported completion rejection and reconcile-before-retry behavior.

## Phase 2 — Minimum Local Runtime ✅ PASS

Qualified local runtime includes:
- Mission Intake
- persisted Agent Registry
- persisted Task Graph / mission state
- durable Event/Audit ledger
- Artifact Registry
- Policy Engine v0
- Budget Manager
- Approval State Manager
- workspace isolation abstraction
- provider adapter interface
- structured tracing with redaction
- restart/resume reconciliation tests

Exit evidence is recorded in `docs/evaluations/PHASE2_COMPLETION.md`. Phase 2 establishes local transactional durability only; it does not claim distributed or production durability.

## Phase 3 — Design Pod ✅ PASS

Completed and qualified:
- [x] A02 Product Architect contract
- [x] A03 System Architect contract
- [x] A04 UI/UX contract
- [x] typed `DesignBundle` contracts
- [x] `schemas/design-bundle.schema.json`
- [x] deterministic cross-role `DesignBundleValidator`
- [x] mission-to-product worker interface
- [x] product-to-architecture worker interface
- [x] product-to-UX worker interface
- [x] bounded Design Pod coordinator
- [x] persisted DesignBundle artifact handoff
- [x] raw-mission end-to-end design evaluation fixture
- [x] contradiction/ambiguity evaluation cases
- [x] bounded role-targeted revision loop
- [x] downstream regeneration after product revision
- [x] no-progress and revision-exhaustion protection

Exit evidence is recorded in `docs/evaluations/PHASE3_COMPLETION.md`. GitHub Actions passed on qualified commit `7d2a9e85ddfde4ad99a339b944864200be3ee662` (run `32814610369`).

Exit criteria satisfied: a raw product idea becomes an internally consistent, traceable and build-ready DesignBundle before coding begins. Every MUST requirement has acceptance coverage and appropriate architecture/UX coverage; invalid cross-role references are rejected automatically.

## Phase 4 — Engineering Pod 🚧 CURRENT

Implement and evaluate:
- [ ] A05 Frontend contract
- [ ] A06 Backend contract
- [ ] A07 Database contract
- [ ] A08 AI & Automation contract
- [ ] typed implementation work-package contract/schema
- [ ] deterministic write-scope/dependency validator
- [ ] isolated workspace/branch assignment model
- [ ] evidence manifest for code/test/artifact completion
- [ ] engineering coordinator with bounded retries/revisions
- [ ] integration plan and conflict handling
- [ ] DesignBundle → engineering work packages fixture
- [ ] controlled-environment integrated application evaluation

Requirements: isolated workspaces/branches, declared write scopes, test/evidence output, dependency review, explicit artifact ownership and no direct production credentials.

Exit criteria: Design Pod artifacts can produce an integrated working application in a controlled environment, and no engineering work package can become complete without declared scope, traceability to DesignBundle requirements and executable evidence.

## Phase 5 — Assurance Pod

Implement and evaluate A09 Security, A10 QA/Test and A12 Red Team/Reviewer. Add executable threat-model test families.

Exit criteria: weak/unsafe work is measurably rejected and corrected rather than merely critiqued.

## Phase 6 — Reliability & Durable Execution

Implement A11 DevOps/Reliability and harden long-running execution: resumable workflows, bounded retries, idempotency/reconciliation, timeouts/circuit breakers, CI/CD, logging/metrics/traces, preview environments and rollback strategy.

A durable workflow engine may be adopted only behind an abstraction after benchmark comparison.

## Phase 7 — Interoperability

Add MCP tool/context adapters, A2A external-agent adapter, provider-specific agent SDK adapters and sandbox-provider adapters where useful. Internal schemas remain canonical.

## Phase 8 — Organizational Memory & Evaluation System

Deliver lesson promotion, memory provenance/integrity, regression corpus, benchmark dashboard, model-router evaluation, false-completion metric, cost/latency/quality metrics and protected evaluation baselines.

Self-improvement may propose changes; it may not silently rewrite governance or its evaluator.

## Phase 9 — Factory Qualification Mission

Run at least one bounded evaluation application exercising product planning, full-stack implementation, migration, security findings, QA regression, parallel work, failure/retry, approval gate and persisted/replayed state.

Exit criteria: compare Factory execution against a simpler baseline and prove the added control-plane/multi-agent complexity earns its cost.

## Phase 10 — Mission 001: Real Estate Intelligence Platform

Only after Factory qualification. Mission-specific roles may include Real Estate Domain, Search/Ranking, SEO, Fraud/Trust and Data Acquisition specialists. The product must not depend on unauthorized copying/republication of third-party listings.

## Phase 11 — Production Hardening

Add multi-mission isolation, stronger identity/capability boundaries, secret management, audit retention, backup/restore, incident response, performance/scale testing, dependency/SBOM controls and production SLOs.

---

# 8. Definition of Done

A meaningful stable release must demonstrate that it can:

1. accept a new mission,
2. create a valid plan/dependency graph,
3. choose single vs multi-agent execution rationally,
4. isolate parallel work,
5. produce integrated code/artifacts,
6. gather executable evidence,
7. reject incorrect/unsafe completion,
8. preserve/recover state after interruption,
9. respect permissions/budgets/approval boundaries,
10. expose an auditable explanation of what happened,
11. swap worker model/provider without redesigning the Factory,
12. finish a qualification mission with better engineering outcome than a simpler baseline.

---

# 9. Instructions for any future language model

Before changing AI Factory:

1. Read `README.md` and this `ROADMAP.md`.
2. Read relevant foundation/architecture/agent documents.
3. Inspect repository state; never rely only on chat memory.
4. Identify the current phase and exit criteria.
5. Prefer completing the current milestone over unrelated work.
6. Record material architecture decisions in ADRs.
7. Do not claim tests/deployments/actions that were not executed and verified.
8. Do not bypass governance or approval boundaries.
9. Update roadmap/status only when evidence genuinely changes.

**Current next action:** define A05–A08 engineering agent contracts and the typed implementation work-package/evidence model, then enforce write-scope and DesignBundle traceability before adding any code-producing worker implementation.
