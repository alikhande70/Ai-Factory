# AI Factory — Master Roadmap v6

> **Status:** Active build  
> **Current phase:** Phase 6 — Reliability & Durable Execution  
> **Architecture:** Hybrid deterministic Control Plane + bounded AI workers  
> **Next milestone:** Implement A11 DevOps/Reliability and deterministic durable-execution guards for retries, timeouts, idempotency, reconciliation and recovery; then qualify restart/rollback behavior with executable evidence.  
> **Repository purpose:** Build a reusable AI-native software organization that can turn product missions into verified software without requiring the human owner to manually coordinate every engineering role.

---

# 1. North Star

AI Factory is not one website, application, real-estate product or e-commerce product. It is a reusable **software-production operating system** that receives a mission and coordinates the work required to produce a tested, reviewable release candidate.

```text
MISSION
  ↓
PRODUCT DEFINITION
  ↓
ARCHITECTURE + UX
  ↓
TASK / DEPENDENCY GRAPH
  ↓
SPECIALIST ENGINEERING
  ↓
EVIDENCE + INTEGRATION
  ↓
SECURITY / QA / RED TEAM
  ↓
RELIABILITY / RELEASE
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
- Review independence is a runtime property, not an agent-count claim.

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

Completed: master roadmap, repository entrypoint, initial organization, human-approval principle and evidence-before-completion principle.

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

Qualified: A01 contract, typed mission/task/agent/artifact/review/action/evidence/objection/event contracts, deterministic state transitions, dependency validation, permission/budget contracts, audit ledger, replayable mission runner, reviewer-independence checks and orchestration evaluations.

## Phase 2 — Minimum Local Runtime ✅ PASS

Qualified: Mission Intake, persisted Agent Registry, task/mission persistence, durable local audit ledger, Artifact Registry, Policy Engine v0, Budget Manager, Approval State Manager, workspace abstraction, provider adapter, structured redacted tracing and restart/resume tests.

Evidence: `docs/evaluations/PHASE2_COMPLETION.md`.

## Phase 3 — Design Pod ✅ PASS

Qualified: A02 Product, A03 System Architecture and A04 UI/UX contracts; typed DesignBundle; deterministic cross-role validation; bounded role-targeted revision; downstream regeneration; ambiguity/contradiction evals; persisted design artifacts.

Evidence: `docs/evaluations/PHASE3_COMPLETION.md`.

## Phase 4 — Engineering Pod ✅ PASS

Qualified:
- [x] A05 Frontend contract
- [x] A06 Backend contract
- [x] A07 Database contract
- [x] A08 AI & Automation contract
- [x] typed implementation work-package/evidence/integration contracts and schemas
- [x] deterministic DesignBundle traceability and MUST ownership checks
- [x] write-scope/dependency conflict validation
- [x] isolated workspace/branch assignment model
- [x] bounded plan and implementation revision loops
- [x] dependency-aware IntegrationManifest with artifact/path ownership checks
- [x] persisted engineering evidence and integration artifacts
- [x] explicit DesignBundle → EngineeringPlan qualification fixture
- [x] controlled frontend/backend/database working application evaluation

Exit evidence: `docs/evaluations/PHASE4_COMPLETION.md`.

Qualified head: `4b2bd2d85e05b444f095c716be96b8c7e40ccb27`; GitHub Actions run `32823650154` succeeded.

Exit criteria satisfied for controlled local qualification: Design Pod artifacts can produce an integrated working application, and engineering work cannot qualify without declared scope, DesignBundle traceability and executable evidence.

## Phase 5 — Assurance Pod ✅ PASS

Qualified:
- [x] typed `AssuranceFinding`, `AssuranceReport`, `AssuranceDecision` and `AcceptanceCoverage`
- [x] A09 Security worker contract
- [x] A10 QA/Test worker contract
- [x] A12 Red-Team worker contract
- [x] deterministic requirement for all three assurance roles
- [x] reviewer-vs-implementer independence guard
- [x] HIGH/CRITICAL findings forced to blocking
- [x] deterministic `PASS` vs `CHANGES_REQUIRED`
- [x] persisted assurance reports and decision through Artifact Registry
- [x] machine-readable Assurance schemas
- [x] executable threat-model test families
- [x] acceptance-criterion coverage accounting for A10
- [x] adversarial integration-seam scenarios for A12
- [x] bounded remediation/re-review loop
- [x] stale prior assurance after corrected engineering artifacts
- [x] release-readiness fingerprint bound to exact reviewed IntegrationManifest
- [x] proof that blocking findings cannot reach release-ready state

Exit evidence: `docs/evaluations/PHASE5_COMPLETION.md`.

Qualified head: `68c8ccef07546dbfcb620cb024d6cac633fba041`; GitHub Actions run `32829332092` succeeded with 94 tests and zero failures under ResourceWarning-as-error.

Exit criteria satisfied for controlled local qualification: weak/unsafe work is measurably rejected and corrected; unresolved blocking findings cannot be promoted to release-ready state.

## Phase 6 — Reliability & Durable Execution 🚧 CURRENT

Goal: make long-running Factory execution recoverable and side-effect safe rather than merely retryable.

Current work:
- [ ] A11 DevOps/Reliability agent contract
- [ ] typed operation, retry, attempt, reconciliation and recovery contracts
- [ ] deterministic retry/reconcile/stop/complete decision engine
- [ ] unknown external-write outcome must reconcile before retry
- [ ] idempotency requirements for side-effecting operations
- [ ] bounded retries and retry-budget exhaustion behavior
- [ ] timeout and circuit-breaker state model
- [ ] resumable execution and restart/recovery evaluation
- [ ] compensation/rollback plan contract for applicable operations
- [ ] structured reliability events/metrics
- [ ] final Phase 6 qualification report and CI evidence

A durable workflow engine may be adopted only behind an abstraction after benchmark comparison; the Factory must not depend on one vendor for canonical semantics.

Exit criteria: after interruption or ambiguous side-effect outcome, canonical state can be recovered without blind duplicate actions; retry/circuit/rollback rules are deterministic, bounded and auditable.

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

**Current next action:** implement A11 and the deterministic reliability contracts/decision engine, then qualify side-effect reconciliation and restart/recovery before expanding deployment machinery.
