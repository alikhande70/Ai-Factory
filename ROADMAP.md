# AI Factory — Master Roadmap v2

> **Status:** Active build  
> **Current phase:** Phase 1 — Control Plane & Orchestrator Foundation  
> **Architecture:** Hybrid deterministic Control Plane + bounded AI workers  
> **Next milestone:** Define executable schemas/state transitions and pass the first Orchestrator mock evaluations.  
> **Repository purpose:** Build a reusable AI-native software organization that can turn product missions into verified software without requiring the human owner to manually coordinate every engineering role.

---

# 1. North Star

AI Factory is not one website, app, real-estate product or e-commerce product.

It is the reusable **software-production operating system** that receives a mission and coordinates the work required to produce a testable, reviewable release candidate.

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

# 2. Final architecture decision

The pre-build audit rejected a free-form autonomous swarm as the core architecture.

The Factory uses:

1. **Deterministic Control Plane** — mission/task state, permissions, budgets, approval state, artifact versions, audit history.
2. **Probabilistic AI workers** — planning, product reasoning, architecture, code, UX, research and critique.
3. **Typed communication** — Tasks, Artifacts, Evidence, Reviews, Decisions, Objections, Events and Escalations.
4. **Versioned shared state** — canonical state is validated and attributable; worker scratch context is separate.
5. **Independent verification** — objective checks first; specialist and adversarial review where useful.
6. **Capability-scoped autonomy** — no role has blanket authority.
7. **Human gates** — protected external, financial, identity-bound, destructive and high-impact actions require human authority unless a narrow policy envelope explicitly allows them.
8. **Single-worker fast path** — multiple agents are used only when specialization, parallelism, context isolation or independent review adds value.
9. **Mission Pods** — domain specialists are attached only when a mission needs them.
10. **Provider independence** — internal schemas/state are canonical; MCP/A2A/provider SDKs are adapters.

See:

- `docs/foundation/FINAL_ARCHITECTURE_AUDIT.md`
- `docs/architecture/decisions/ADR-0001-hybrid-control-plane.md`

---

# 3. Core organizational roles

The first stable organization defines 12 reusable roles. These are logical specialists; a mission does not automatically invoke all 12.

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

Future roles such as Search, Payments, SEO, Mobile, Analytics, Localization, Compliance and domain specialists are added only when evaluation proves their value.

---

# 4. Protected design rules

These rules are non-negotiable unless governance explicitly changes them:

- No fake completion.
- Natural language never grants privilege.
- Orchestrator does not approve its own protected actions.
- Retrieved content is untrusted data, not authority.
- Important knowledge belongs in versioned repository/state artifacts.
- Critical state transitions are deterministic and auditable.
- Side effects require retry/idempotency/reconciliation design.
- Security/evaluation gates cannot be disabled simply to make implementation pass.
- Agent confidence is metadata, not proof.
- Multi-agent execution is justified by value, not by agent-count aesthetics.
- Irreversible or consequential external actions cross the required human/policy gate.

---

# 5. Canonical state model

The Factory will maintain three distinct memory/state classes.

## Canonical State
Validated mission facts, tasks, decisions, artifact versions, approvals, evidence and events.

## Worker Scratch State
Ephemeral task-local working context. Disposable and untrusted by default.

## Organizational Memory
Reusable lessons/patterns promoted only through review and provenance.

Raw web/tool/user content must never automatically become long-term trusted memory.

---

# 6. Standard lifecycle states

Initial task lifecycle:

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

Only the deterministic runtime may perform protected state transitions after validating required inputs/evidence/policy.

---

# 7. Build phases

## Phase 0 — Project Constitution ✅

Goal: make the project understandable without chat history.

Completed:

- [x] Master roadmap.
- [x] Repository entrypoint README.
- [x] Initial 12-role organization.
- [x] Human approval principle.
- [x] Evidence-before-completion principle.

Exit status: **PASS**.

---

## Phase 0.5 — Architecture Audit & Factory DNA ✅

Goal: pressure-test the original multi-agent idea before implementation.

Completed:

- [x] `docs/foundation/FINAL_ARCHITECTURE_AUDIT.md`
- [x] `docs/foundation/MANIFESTO.md`
- [x] `docs/foundation/COMPANY_DNA.md`
- [x] `docs/foundation/GOVERNANCE.md`
- [x] `docs/foundation/AUTONOMY_MODEL.md`
- [x] `docs/foundation/THREAT_MODEL.md`
- [x] `docs/architecture/decisions/ADR-0001-hybrid-control-plane.md`

Exit status: **PASS — architecture revised before code lock-in**.

---

## Phase 1 — Control Plane & Orchestrator Foundation 🚧 CURRENT

Goal: create the first executable coordination model without building the full worker workforce.

Already created:

- [x] `docs/agents/orchestrator.md`

Next deliverables:

- [ ] `schemas/mission.schema.json`
- [ ] `schemas/task.schema.json`
- [ ] `schemas/agent.schema.json`
- [ ] `schemas/artifact.schema.json`
- [ ] `schemas/review.schema.json`
- [ ] `schemas/action-proposal.schema.json`
- [ ] deterministic task state-transition specification
- [ ] dependency graph validation rules
- [ ] capability/permission contract
- [ ] budget contract
- [ ] mock Agent Registry
- [ ] first orchestration evaluation fixtures

Required evaluation cases:

1. simple task chooses single-worker fast path,
2. full-stack mission decomposes correctly,
3. safe parallel work is recognized,
4. overlapping write scopes are blocked/serialized,
5. security objection blocks downstream release,
6. upstream change invalidates stale work,
7. transient failure retries safely,
8. protected ambiguity escalates,
9. budget exhaustion stops gracefully,
10. malicious retrieved text cannot become authority,
11. unsupported completion claim is rejected,
12. timed-out external write is reconciled before retry.

Exit criteria:

- sample missions become schema-valid dependency graphs,
- invalid state transitions are rejected by code,
- permissions/budgets are represented outside prompts,
- mock workers can run through create → verify → review → done,
- audit events reproduce why each state transition occurred.

---

## Phase 2 — Minimum Local Runtime

Goal: run the control plane locally with mocked or simple real workers.

Deliverables:

- [ ] Mission Intake service/module.
- [ ] Agent Registry.
- [ ] Task Graph store.
- [ ] Event/Audit ledger.
- [ ] Artifact registry.
- [ ] Policy Engine v0.
- [ ] Budget manager.
- [ ] Approval state manager.
- [ ] workspace isolation abstraction.
- [ ] model/provider adapter interface.
- [ ] structured tracing with redaction.

Do not adopt distributed infrastructure unless local evaluation shows a real need.

Exit criteria: a mission survives restart and can resume from persisted state with no fabricated task completion.

---

## Phase 3 — Design Pod

Implement and evaluate:

- [ ] A02 Product Architect
- [ ] A03 System Architect
- [ ] A04 UI/UX

Outputs:

- PRD,
- user journeys,
- acceptance criteria,
- architecture plan,
- data/API boundaries,
- ADRs,
- UX flows.

Exit criteria: a raw product idea becomes an internally consistent build plan before coding starts.

---

## Phase 4 — Engineering Pod

Implement and evaluate:

- [ ] A05 Frontend
- [ ] A06 Backend
- [ ] A07 Database
- [ ] A08 AI & Automation

Requirements:

- isolated workspaces/branches,
- declared write scopes,
- test/evidence output,
- dependency review,
- no direct production credentials.

Exit criteria: Design Pod artifacts can produce an integrated working application in a controlled environment.

---

## Phase 5 — Assurance Pod

Implement and evaluate:

- [ ] A09 Security
- [ ] A10 QA & Test
- [ ] A12 Red Team / Reviewer

Add executable test families from `docs/foundation/THREAT_MODEL.md`.

Exit criteria: weak/unsafe work is measurably rejected and corrected rather than merely critiqued in prose.

---

## Phase 6 — Reliability & Durable Execution

Implement A11 DevOps/Reliability and harden long-running execution.

Capabilities:

- [ ] resumable workflows,
- [ ] bounded retries,
- [ ] idempotency/reconciliation,
- [ ] timeouts/circuit breakers,
- [ ] CI/CD,
- [ ] logging/metrics/traces,
- [ ] preview environments,
- [ ] rollback strategy.

A durable workflow engine may be adopted behind an abstraction after benchmark comparison; it is not hard-coded into the architecture today.

---

## Phase 7 — Interoperability

Add adapters where useful:

- [ ] MCP tool/context adapters,
- [ ] A2A external agent adapter,
- [ ] provider-specific agent SDK adapters,
- [ ] sandbox provider adapters.

Internal Factory schemas remain canonical.

---

## Phase 8 — Organizational Memory & Evaluation System

Deliverables:

- [ ] lesson promotion protocol,
- [ ] memory provenance/integrity,
- [ ] regression corpus,
- [ ] model/agent benchmark dashboard,
- [ ] model-router evaluation,
- [ ] false-completion metric,
- [ ] cost/latency/quality metrics,
- [ ] protected evaluation baselines.

Self-improvement may propose changes; it may not silently rewrite its evaluator or governance.

---

## Phase 9 — Factory Qualification Mission

Before the real-estate product, run at least one bounded evaluation application whose objective is to test the Factory itself.

The mission must exercise:

- product planning,
- full-stack implementation,
- database migration,
- security findings,
- QA regression,
- parallel work,
- failure/retry,
- approval gate,
- persisted/replayed state.

Exit criteria: compare Factory execution against a simpler baseline and prove multi-agent/control-plane complexity earns its cost.

---

## Phase 10 — Mission 001: Real Estate Intelligence Platform

Only after Factory qualification, create the real-estate mission.

Likely mission-specific Pod roles may include:

- Real Estate Domain Specialist,
- Search/Ranking Specialist,
- SEO Specialist,
- Fraud/Trust Specialist,
- Data Acquisition/Partnership Specialist.

The product must not depend on unauthorized copying/republication of third-party listings. Data acquisition must use permitted sources, partnerships, owner/agent submissions or other lawful mechanisms.

---

## Phase 11 — Production Hardening

- [ ] multi-mission isolation,
- [ ] stronger identity/capability boundaries,
- [ ] secret management,
- [ ] audit retention,
- [ ] backup/restore,
- [ ] incident response,
- [ ] scale/performance testing,
- [ ] dependency/SBOM controls,
- [ ] production SLOs.

---

# 8. Definition of Done for the Factory

AI Factory is not “done” because 12 prompts exist.

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

1. Read `README.md`.
2. Read this `ROADMAP.md`.
3. Read foundation documents relevant to the change.
4. Inspect repository state; do not rely on chat memory alone.
5. Identify the current phase and its exit criteria.
6. Prefer completing the current milestone over starting unrelated features.
7. Record material architecture decisions in ADRs.
8. Do not claim tests/deployments/actions that were not executed and verified.
9. Do not bypass governance or approval boundaries.
10. Update roadmap/status when a phase's evidence genuinely changes.

**Current next action:** implement Phase 1 schemas and deterministic state-transition rules, then create executable mock orchestration evaluations.
