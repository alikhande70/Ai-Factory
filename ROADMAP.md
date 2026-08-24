# AI Factory — Master Roadmap

> **Status:** Active foundation phase  
> **Current phase:** Phase 0 — Project Foundation  
> **Next milestone:** Define and implement the Orchestrator Agent contract  
> **Repository purpose:** Build a reusable, AI-native software factory that can design, build, test, review, and prepare software products through a coordinated team of specialized agents.

---

# 1. Why this project exists

AI Factory is **not a single application** and is not tied to real estate, e-commerce, trading, or any other one business domain.

It is a reusable **software-production system** whose job is to accept a product mission and coordinate specialized AI agents that can take that mission from idea to a tested, reviewable, deployable software product.

The long-term goal is:

> **User intent → Product specification → Architecture → UX/UI → Frontend → Backend → Database → AI features → Security review → QA → Integration → Deployment preparation → Maintenance**

The human owner should not need to manually coordinate every technical role. The factory should perform most project decomposition, delegation, implementation, verification, and handoff itself.

However, the system must never pretend to have completed actions it did not actually perform. Human approval remains mandatory for sensitive external actions such as production deployment, secrets, billing, destructive data operations, legal approvals, domain ownership, or other account-level decisions.

---

# 2. Product vision

AI Factory should eventually behave like a small autonomous software company.

A user should be able to provide a mission such as:

- Build a real-estate marketplace.
- Build an e-commerce platform.
- Build a SaaS product.
- Build a booking system.
- Build an analytics dashboard.
- Build a trading-support application.
- Build an internal business automation tool.

The factory should then:

1. Understand the real business objective.
2. Identify missing requirements.
3. Detect risks and contradictions.
4. Create a product specification.
5. Design system architecture.
6. Break the project into executable work packages.
7. Assign work to the correct specialist agents.
8. Produce code and technical artifacts.
9. Test the result.
10. Review security and architecture.
11. Reject weak work automatically.
12. Integrate approved work.
13. Prepare a release candidate.
14. Produce deployment instructions or execute permitted deployment actions behind explicit approval gates.
15. Maintain a project memory so another model can continue without rediscovering the project.

---

# 3. What AI Factory is NOT

AI Factory must not become:

- A collection of unrelated prompts.
- A chat wrapper pretending to be autonomous.
- A system that generates code without tests.
- A system that allows every agent to modify everything.
- A system that deploys blindly to production.
- A system that stores secrets in prompts or source control.
- A system that accepts an agent's claim that work is complete without verification.
- A project specialized only for one business idea.
- A 50-agent swarm created before the coordination model works.

The factory starts small, proves the orchestration architecture, then expands only when evidence shows that additional specialization improves outcomes.

---

# 4. Core design principles

## 4.1 Intent completion over prompt completion
Agents must solve the intended product outcome, not merely answer the literal request.

## 4.2 Evidence before completion
An implementation is not complete because an agent says so. Tests, generated artifacts, diffs, logs, or other evidence must support completion.

## 4.3 Separation of responsibilities
Planning, implementation, review, security, and release approval should not all be performed by the same agent without independent checks.

## 4.4 Least privilege
Each agent receives only the tools and repository permissions required for its role.

## 4.5 Human approval gates
Sensitive actions require explicit approval.

## 4.6 Reusable agents, domain-specific missions
Most agents belong to the factory. Domain specialists are attached to individual missions when needed.

## 4.7 Test-first verification culture
Every major feature must have acceptance criteria and a verification path before implementation begins.

## 4.8 Traceability
Every meaningful decision should be traceable from user requirement → task → implementation → test → review → release.

## 4.9 Controlled autonomy
Autonomy is earned by passing evaluations. More autonomy is granted only when the system consistently performs well.

## 4.10 No fake completion
If an external action cannot be performed, the system must mark it as pending instead of claiming it succeeded.

---

# 5. Initial agent team

The first stable release targets **12 reusable core agents**.

The exact implementation contracts for these agents will live under `docs/agents/`.

## A01 — Orchestrator Agent
**Role:** Factory coordinator and work dispatcher.

Responsibilities:
- Interpret the project mission.
- Maintain global project state.
- Decompose work.
- Build dependency graphs.
- Assign tasks.
- Detect blocked tasks.
- Trigger review gates.
- Prevent conflicting parallel changes.
- Decide when work must be escalated to the user.

The Orchestrator does **not** automatically approve its own work.

## A02 — Product Architect Agent
**Role:** Convert business intent into a buildable product definition.

Responsibilities:
- Product requirements.
- Personas and user journeys.
- Feature prioritization.
- Scope control.
- Acceptance criteria.
- Business-rule clarification.

## A03 — System Architect Agent
**Role:** Design the technical system.

Responsibilities:
- Service boundaries.
- Technology choices.
- API architecture.
- Scaling model.
- Reliability strategy.
- Architecture Decision Records (ADRs).

## A04 — UI/UX Agent
**Role:** Design product interaction and interface systems.

Responsibilities:
- Information architecture.
- User flows.
- Wireframes/specifications.
- Accessibility.
- Responsive behavior.
- Design-system rules.

## A05 — Frontend Agent
**Role:** Implement client-facing applications.

Responsibilities:
- UI implementation.
- State management.
- API integration.
- Accessibility implementation.
- Frontend tests.
- Performance checks.

## A06 — Backend Agent
**Role:** Implement server-side application logic.

Responsibilities:
- APIs.
- Business logic.
- Authentication integration.
- Background jobs.
- Service integrations.
- Backend tests.

## A07 — Database Agent
**Role:** Own data architecture.

Responsibilities:
- Data models.
- Schema design.
- Indexing.
- Migrations.
- Query quality.
- Data consistency.
- Backup/restore requirements.

## A08 — AI & Automation Agent
**Role:** Add AI-native capabilities and workflow automation.

Responsibilities:
- Model integration.
- Agent/tool workflows.
- Retrieval systems.
- Prompt/version management.
- Evaluation datasets.
- Cost/latency controls.

## A09 — Security Agent
**Role:** Independent security reviewer.

Responsibilities:
- Threat modeling.
- Authentication/authorization review.
- Secret-handling review.
- Dependency risks.
- Input validation.
- Abuse cases.
- OWASP-oriented checks.

## A10 — QA & Test Agent
**Role:** Verify that implementation matches requirements.

Responsibilities:
- Unit/integration/end-to-end test planning.
- Regression testing.
- Acceptance testing.
- Bug reproduction.
- Test evidence.

## A11 — DevOps / Reliability Agent
**Role:** Build reliable delivery infrastructure.

Responsibilities:
- CI/CD.
- Containers.
- Environments.
- Deployment configuration.
- Logging.
- Monitoring.
- Rollback strategy.

## A12 — Red-Team / Reviewer Agent
**Role:** Independent final critic.

Responsibilities:
- Challenge assumptions.
- Review cross-agent work.
- Find architecture mistakes.
- Detect missing edge cases.
- Reject weak completion claims.
- Perform final release-readiness reviews.

---

# 6. Optional future specialist agents

These agents are **not part of the first build**. They are added only when needed:

- Mobile App Agent.
- Search / Ranking Agent.
- Payments Agent.
- Analytics Agent.
- Data Engineering Agent.
- Localization Agent.
- Performance Agent.
- SEO Agent.
- Compliance Agent.
- Domain Expert Agents.
- Growth / Experimentation Agent.
- Technical Writer Agent.

This prevents unnecessary multi-agent complexity during the foundation phase.

---

# 7. Factory execution model

Every mission should move through the same high-level lifecycle.

```text
USER MISSION
    ↓
ORCHESTRATOR
    ↓
PRODUCT DISCOVERY
    ↓
REQUIREMENTS + ACCEPTANCE CRITERIA
    ↓
SYSTEM / DATA / UX ARCHITECTURE
    ↓
DEPENDENCY GRAPH + EXECUTION PLAN
    ↓
SPECIALIST IMPLEMENTATION AGENTS
    ↓
AUTOMATED TESTS
    ↓
SECURITY REVIEW
    ↓
RED-TEAM REVIEW
    ↓
INTEGRATION
    ↓
RELEASE CANDIDATE
    ↓
HUMAN APPROVAL GATE WHEN REQUIRED
    ↓
DEPLOYMENT / HANDOFF
    ↓
MONITORING + MAINTENANCE
```

No implementation task should enter the execution stage without:

- a clear owner,
- explicit inputs,
- expected outputs,
- acceptance criteria,
- dependencies,
- verification method,
- allowed tools,
- completion evidence.

---

# 8. Standard task contract

Every agent task will eventually be represented by a machine-readable task object.

Minimum fields:

```yaml
id: TASK-0001
title: Short task title
mission_id: MISSION-001
owner_agent: A05-FRONTEND
status: READY
priority: HIGH
inputs: []
dependencies: []
objective: "What outcome must be achieved"
constraints: []
acceptance_criteria: []
allowed_tools: []
expected_artifacts: []
verification: []
reviewers: []
completion_evidence: []
```

Statuses should eventually include:

```text
BACKLOG
READY
IN_PROGRESS
BLOCKED
REVIEW
CHANGES_REQUESTED
VERIFIED
DONE
FAILED
CANCELLED
```

---

# 9. Standard agent contract

Every agent definition must contain at least:

- Agent ID.
- Role.
- Mission.
- Scope.
- Responsibilities.
- Inputs.
- Outputs.
- Tools.
- Permissions.
- Forbidden actions.
- Dependencies.
- Handoff protocol.
- Quality gates.
- Failure modes.
- Escalation rules.
- Evaluation tests.

Agents should be replaceable. Project knowledge must live in repository artifacts and structured state, not only inside one model's chat history.

---

# 10. Human approval boundaries

AI Factory should automate aggressively **inside safe boundaries**.

Explicit human approval is required before:

- Production deployment.
- Purchasing paid infrastructure.
- Changing billing settings.
- Registering or transferring domains.
- Using production credentials.
- Creating/rotating sensitive secrets.
- Destructive production-database operations.
- Sending external messages in the owner's name.
- Accepting legal agreements.
- Financial transactions.
- Actions subject to identity, age, or regulatory eligibility.

The factory may prepare these operations, but must mark them `AWAITING_HUMAN_APPROVAL` until authorized.

---

# 11. Planned repository structure

The repository should evolve toward:

```text
Ai-Factory/
│
├── README.md
├── ROADMAP.md
├── CONTRIBUTING.md
├── SECURITY.md
│
├── docs/
│   ├── architecture/
│   │   ├── overview.md
│   │   └── decisions/
│   ├── agents/
│   │   ├── orchestrator.md
│   │   ├── product-architect.md
│   │   ├── system-architect.md
│   │   └── ...
│   ├── protocols/
│   │   ├── task-contract.md
│   │   ├── handoff-protocol.md
│   │   ├── review-protocol.md
│   │   └── approval-gates.md
│   ├── missions/
│   │   └── README.md
│   └── evaluations/
│
├── schemas/
│   ├── agent.schema.json
│   ├── task.schema.json
│   ├── mission.schema.json
│   └── artifact.schema.json
│
├── factory/
│   ├── orchestrator/
│   ├── runtime/
│   ├── state/
│   ├── routing/
│   ├── tools/
│   └── approvals/
│
├── agents/
│   ├── product/
│   ├── architecture/
│   ├── uiux/
│   ├── frontend/
│   ├── backend/
│   ├── database/
│   ├── ai/
│   ├── security/
│   ├── qa/
│   ├── devops/
│   └── reviewer/
│
├── templates/
│   ├── web-app/
│   ├── api/
│   └── mission/
│
├── evals/
│   ├── orchestration/
│   ├── coding/
│   ├── review/
│   └── security/
│
├── tests/
│
├── examples/
│
└── .github/
    └── workflows/
```

This is the target architecture, not a requirement to create every directory immediately.

---

# 12. Roadmap phases

## Phase 0 — Foundation and project constitution

**Goal:** Create a source of truth so every future model understands the project before touching implementation.

Deliverables:
- [x] Master `ROADMAP.md`.
- [ ] Root `README.md`.
- [ ] Project principles.
- [ ] Repository structure bootstrap.
- [ ] Mission / Agent / Task terminology.
- [ ] Contribution rules.
- [ ] Security baseline.

Exit criteria:
- A new model can read repository documentation and accurately explain the project, current phase, next milestone, safety boundaries, and agent architecture without relying on chat history.

---

## Phase 1 — Orchestrator specification

**Goal:** Design the central coordination contract before building specialist agents.

Deliverables:
- [ ] `docs/agents/orchestrator.md`.
- [ ] Orchestrator state model.
- [ ] Mission-decomposition algorithm.
- [ ] Dependency-graph rules.
- [ ] Task-routing rules.
- [ ] Conflict-detection rules.
- [ ] Escalation policy.
- [ ] Approval-gate protocol.
- [ ] Orchestrator evaluation suite.

Key questions to solve:
- How does the Orchestrator know a requirement is underspecified?
- When can tasks run in parallel?
- How are conflicting changes detected?
- When should an agent be retried versus replaced?
- How does the Orchestrator know a task is actually complete?

Exit criteria:
- Given a sample product mission, the Orchestrator can produce a valid dependency graph and task set without writing product code.

---

## Phase 2 — Shared schemas and communication protocol

**Goal:** Give all agents one formal language.

Deliverables:
- [ ] `mission.schema.json`.
- [ ] `agent.schema.json`.
- [ ] `task.schema.json`.
- [ ] `artifact.schema.json`.
- [ ] Handoff protocol.
- [ ] Completion-evidence protocol.
- [ ] Review-response protocol.
- [ ] Blocking/escalation protocol.

Exit criteria:
- Agent outputs can be validated programmatically.
- Invalid or incomplete handoffs are rejected automatically.

---

## Phase 3 — Factory runtime / control plane

**Goal:** Implement the minimum software required to run the agent system.

Initial capabilities:
- [ ] Mission intake.
- [ ] Agent registry.
- [ ] Task queue.
- [ ] Dependency tracking.
- [ ] State persistence.
- [ ] Artifact registry.
- [ ] Execution logs.
- [ ] Approval states.
- [ ] Retry/failure handling.

The runtime should initially be simple and observable. Do not introduce distributed infrastructure until necessary.

Exit criteria:
- A test mission can be created, decomposed, routed through mocked agents, reviewed, and closed with a reproducible activity log.

---

## Phase 4 — Product, architecture and UX agents

**Goal:** Make the factory capable of designing a product before coding it.

Implement:
- [ ] A02 Product Architect.
- [ ] A03 System Architect.
- [ ] A04 UI/UX Agent.

Required outputs:
- Product Requirements Document (PRD).
- User stories.
- Acceptance criteria.
- System architecture.
- Data/API boundaries.
- UX flows.
- Architecture decisions.

Exit criteria:
- A raw product idea can be converted into a coherent, reviewable implementation plan.

---

## Phase 5 — Core implementation agents

**Goal:** Produce working software.

Implement:
- [ ] A05 Frontend.
- [ ] A06 Backend.
- [ ] A07 Database.
- [ ] A08 AI & Automation.

Requirements:
- Agents operate on assigned scopes.
- Changes are attributable to tasks.
- Tests are included with implementation.
- Agents may not self-certify final release quality.

Exit criteria:
- Factory can generate and integrate a small full-stack application from an approved specification.

---

## Phase 6 — Independent verification agents

**Goal:** Prevent plausible-looking but broken output.

Implement:
- [ ] A09 Security Agent.
- [ ] A10 QA Agent.
- [ ] A12 Red-Team Agent.

Quality gates:
- Functional acceptance.
- Regression tests.
- Security review.
- Dependency checks.
- Edge-case analysis.
- Architecture conformance.

Exit criteria:
- Intentionally seeded bugs and security weaknesses are detected with acceptable reliability.

---

## Phase 7 — DevOps and release engineering

**Goal:** Turn verified builds into reproducible releases.

Implement A11 DevOps / Reliability Agent.

Deliverables:
- [ ] CI pipeline.
- [ ] Test automation.
- [ ] Build artifacts.
- [ ] Environment templates.
- [ ] Deployment plans.
- [ ] Rollback procedures.
- [ ] Monitoring requirements.

Exit criteria:
- A release candidate can be built repeatedly from source with documented deployment and rollback steps.

---

## Phase 8 — Project memory and continuity

**Goal:** Any future AI model should be able to continue the project safely.

The factory must persist:
- Current mission state.
- Decisions.
- Requirements.
- Architecture.
- Agent assignments.
- Completed tasks.
- Failed approaches.
- Known issues.
- Release history.

Repository documentation is the source of truth. Chat context is temporary convenience only.

Deliverables:
- [ ] Project-state file/schema.
- [ ] Decision log / ADRs.
- [ ] Mission progress files.
- [ ] Handoff summary generator.

Exit criteria:
- A fresh model can continue an interrupted mission from repository state alone.

---

## Phase 9 — Factory evaluation project

**Goal:** Test AI Factory on a deliberately small but complete application before attempting a major commercial product.

The test app must include:
- Authentication.
- CRUD workflow.
- Database.
- Search/filter.
- Responsive UI.
- API.
- Tests.
- CI.
- Security review.
- Deployment candidate.

Purpose:
Validate the **factory**, not the sample application's business value.

Exit criteria:
- The complete lifecycle passes without manual coordination of each specialist agent.

---

## Phase 10 — Mission 001: Real Estate Intelligence Platform

**Working reference mission, not the identity of AI Factory.**

Target direction:
A specialized property-discovery and decision-support platform, initially oriented toward the Iranian real-estate market.

Potential capabilities:
- Property listings supplied by owners, agencies and permitted feeds.
- AI-assisted listing normalization.
- Duplicate detection.
- Natural-language property search.
- Area/neighborhood intelligence.
- Comparable-property analysis.
- Price reasoning where reliable data exists.
- Agent/agency dashboards.
- Saved searches and alerts.
- Lead routing.

Important data rule:
The product must not assume that content can be copied from third-party marketplaces. Data ingestion must respect permissions, APIs, feeds, partnerships, applicable terms and rights.

This mission will be specified in its own mission directory only after the factory passes Phase 9.

Exit criteria:
- A production-quality MVP can accept real users and survive QA/security/reliability gates.

---

## Phase 11 — Parallel agent execution

**Goal:** Improve speed without corrupting quality.

Capabilities:
- Parallel independent workstreams.
- File ownership / edit locks.
- Merge-conflict prevention.
- Dependency-aware scheduling.
- Dynamic task reprioritization.
- Reviewer assignment.

Exit criteria:
- Parallel execution produces equal or better quality than sequential execution in controlled evaluations.

---

## Phase 12 — Evaluation-driven self-improvement

**Goal:** Let the factory improve its own workflows safely.

Allowed:
- Analyze historical task results.
- Identify recurring failures.
- Recommend changes to prompts, routing and evaluation rules.
- Open proposals/PRs for its own runtime.
- Run regression evaluations against proposed changes.

Not allowed:
- Silently rewrite its own safety rules.
- Silently grant itself more permissions.
- Bypass human approval gates.
- Deploy self-modifications directly to production without review.

Exit criteria:
- Workflow improvements can demonstrate measurable gains against a stable evaluation suite.

---

## Phase 13 — Production hardening

**Goal:** Make AI Factory itself reliable enough for sustained use.

Areas:
- Observability.
- Cost controls.
- Rate limiting.
- Failure isolation.
- Agent timeouts.
- Tool permission management.
- Secret management.
- Backup/recovery.
- Audit logs.
- Versioning.
- Reproducible environments.

Exit criteria:
- Factory failures are diagnosable and recoverable without corrupting active missions.

---

# 13. Quality model

Every mission must pass a hierarchy of gates.

## Gate 1 — Product correctness
Does the proposed feature solve the intended user problem?

## Gate 2 — Architecture correctness
Does the design fit the functional and non-functional requirements?

## Gate 3 — Implementation correctness
Does the code match the approved design?

## Gate 4 — Automated verification
Do tests pass and cover critical behavior?

## Gate 5 — Security review
Are major abuse/security paths controlled?

## Gate 6 — Red-team review
What was missed? What assumption is weakest?

## Gate 7 — Release readiness
Can the product be deployed, monitored and rolled back safely?

No agent should skip a gate merely because previous output looks convincing.

---

# 14. Definition of Done

A feature is `DONE` only when:

1. Requirement is traceable.
2. Acceptance criteria are satisfied.
3. Required code/artifacts exist.
4. Relevant automated tests pass.
5. Required reviewers approve.
6. Security checks pass where applicable.
7. Documentation is updated.
8. Completion evidence is recorded.
9. No unresolved blocker is hidden.

A mission is `RELEASE_READY` only when all critical tasks are verified and deployment prerequisites are explicit.

---

# 15. Failure handling

Agents must not improvise silently when critical inputs are missing.

A task should become `BLOCKED` when:
- Required input is unavailable.
- Requirement conflicts with another requirement.
- Required permission is unavailable.
- External dependency fails.
- Security/legal approval is required.

The Orchestrator then chooses one of:
- Request information.
- Re-plan.
- Assign another specialist.
- Use an approved fallback.
- Defer the feature.
- Escalate to human approval.

Repeated blind retries are not an acceptable failure strategy.

---

# 16. Autonomy levels

AI Factory should evolve through explicit autonomy levels.

## Level 0 — Advisory
Agents recommend; human performs actions.

## Level 1 — Structured planning
Agents create complete plans and artifacts.

## Level 2 — Controlled repository execution
Agents can implement and test changes in isolated branches/workspaces.

## Level 3 — Autonomous build + review
Factory coordinates implementation, testing and internal review, producing a release candidate.

## Level 4 — Gated operational execution
Factory may perform approved CI/deployment operations behind explicit permission gates.

## Level 5 — Mature continuous factory
Factory can maintain multiple missions with monitoring, evaluation and controlled self-improvement.

**Current target:** Reach Level 3 reliably before considering Level 4.

---

# 17. Cost philosophy

The early factory should favor:
- Simple architecture.
- Local/open-source tooling where practical.
- Minimal paid infrastructure.
- Observable execution.
- Usage limits.
- Model routing based on task difficulty.

Do not use an expensive model for work a cheaper model can reliably complete.

Future orchestration should support model specialization:
- High-reasoning model for architecture/review.
- Coding model for implementation.
- Fast model for classification/routing.
- Specialized tools for deterministic tasks.

---

# 18. Security philosophy

The factory assumes agents can make mistakes.

Therefore:
- Secrets never live in prompts or committed source.
- Production credentials use a dedicated secret manager.
- Agents receive scoped credentials.
- Shell/tool access is sandboxed where possible.
- Dangerous commands require policy checks.
- Production write access is gated.
- Dependency additions are reviewed.
- External code is treated as untrusted until inspected.

---

# 19. Model handoff protocol

## Mandatory instruction for every future AI model

Before making architectural or implementation changes in this repository:

1. Read `ROADMAP.md`.
2. Read the root `README.md` when it exists.
3. Identify the **Current Phase**.
4. Read relevant files under `docs/`.
5. Inspect current repository state instead of assuming files exist.
6. Preserve locked architectural decisions unless evidence justifies an ADR proposing change.
7. Do not jump directly to a business application before the factory foundation is ready.
8. Do not create additional agents merely for impressive agent count.
9. Provide verification evidence for implementation claims.
10. Update project-state documentation when completing a milestone.

If chat instructions conflict with repository state, clarify the intended change before destroying established project architecture.

---

# 20. Current project state

At the time this roadmap was created:

- GitHub repository exists.
- Repository name: **Ai-Factory**.
- The software factory concept is approved.
- The initial 12-agent organization is approved at a high level.
- No agent implementation should be considered complete yet.
- No runtime architecture is locked yet.
- No technology stack is locked yet.
- The real-estate platform is a future reference mission, not the core repository purpose.

### Current phase

**PHASE 0 — FOUNDATION**

### Immediate next deliverable

**A01 — Orchestrator Agent Specification**

The next task should define in detail:
- Orchestrator inputs and outputs.
- Mission intake format.
- Task decomposition rules.
- Dependency graph.
- Agent routing.
- Context/memory rules.
- Parallelization rules.
- Verification requirements.
- Failure/retry behavior.
- Human approval gates.
- Orchestrator state machine.
- Evaluation scenarios.

Do not implement all 12 agents before this specification is reviewed.

---

# 21. North-star success criteria

AI Factory succeeds when a user can provide a product mission and the system can reliably produce a release candidate with minimal human coordination while maintaining:

- Correctness.
- Traceability.
- Security.
- Maintainability.
- Testability.
- Clear human approval boundaries.
- Reusable agent architecture.
- Continuity across different AI models and sessions.

The final product is not “many AI agents.”

The final product is a **reliable software-production organization implemented in software**.
