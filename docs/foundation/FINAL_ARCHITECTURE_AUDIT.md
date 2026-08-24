# AI Factory — Final Architecture Audit

**Date:** 2026-08-25  
**Status:** Approved foundation decision  
**Scope:** Pre-implementation audit of the AI Factory architecture before building the runtime and agents.

## Executive decision

AI Factory will **not** be implemented as a free-form swarm of autonomous chat agents.

The approved architecture is a **hybrid AI Software Factory OS** with:

1. a deterministic Control Plane,
2. bounded specialist agents,
3. typed tasks/events instead of unrestricted agent chat,
4. versioned shared project state,
5. independent verification and adversarial review,
6. policy-enforced permissions and human approval gates,
7. durable/replayable execution,
8. model/provider independence,
9. mission-specific Pods added only when useful,
10. evaluation-driven expansion rather than agent-count growth.

The 12 core agents remain useful as **organizational roles**, but they are not required to be 12 continuously running processes. A simple mission may use one or two roles; a complex mission may activate many.

---

## What was strong in the original design

The first roadmap already made several correct architectural choices:

- role specialization,
- evidence before completion,
- least privilege,
- independent security/review roles,
- human approval for sensitive external actions,
- project knowledge stored in repository artifacts,
- gradual expansion instead of immediately creating a 50-agent swarm.

These principles are retained.

---

## Critical weaknesses discovered in the audit

### 1. Multi-agent is not automatically better

Using more agents can increase computation, communication overhead, duplicated reasoning and error propagation. For simple work, a strong single worker can be more efficient and sometimes more accurate.

**Correction:** add a `SINGLE_AGENT_FAST_PATH`. Multi-agent execution is chosen only when specialization, parallelism, independent verification or context isolation provides measurable value.

### 2. A powerful Orchestrator becomes a single point of failure

If one LLM plans, grants permissions, modifies state, judges quality and approves release, the apparent multi-agent system is still controlled by one probabilistic authority.

**Correction:** split responsibilities:

- **Planner/Orchestrator:** proposes and coordinates.
- **Deterministic Policy Engine:** decides what is allowed.
- **State Engine:** controls canonical state transitions.
- **Review/Evidence Gates:** decide whether work qualifies for acceptance.

The Orchestrator cannot override these components.

### 3. A mutable shared blackboard is too dangerous

An unrestricted shared memory allows stale facts, prompt injection, accidental overwrite and memory poisoning to propagate to every agent.

**Correction:** shared state is divided into three layers:

- **Canonical State:** validated, versioned, append-audited facts and artifacts.
- **Agent Scratch State:** private and disposable working context.
- **Organizational Memory:** lessons promoted only after review.

Raw user/web/tool content is never automatically promoted into trusted long-term memory.

### 4. Reviewer independence can be fake

Two agents using the same model, same context and same assumptions can make correlated mistakes.

**Correction:** critical reviews use at least one of:

- different prompt/context isolation,
- different model configuration or provider when practical,
- deterministic tests/static analysis,
- adversarial test cases,
- independent evidence generation.

`AGENT_COUNT != INDEPENDENCE`.

### 5. Free-form inter-agent conversation destroys traceability

Long chat chains are difficult to validate, replay and debug.

**Correction:** agents communicate primarily through typed `Task`, `Artifact`, `Review`, `Decision`, `Event` and `Escalation` objects. Free-form discussion may occur inside a bounded deliberation task, but only structured conclusions become canonical state.

### 6. Retries can duplicate real actions

A failed network response does not prove an external action failed. Blind retry can create duplicate deployments, messages, records or purchases.

**Correction:** side-effecting tools require:

- idempotency keys where supported,
- preconditions,
- post-action verification,
- explicit retry policies,
- compensation/rollback strategy when possible.

### 7. Human approval itself can be manipulated

If an LLM writes the approval dialog, malicious retrieved content can influence the wording and hide the true action.

**Correction:** approval screens must be rendered from a machine-readable `ActionProposal` by deterministic UI code. The user sees target, scope, irreversible effects, cost, permissions and exact operation separately from model-authored explanation.

### 8. Agent loops can become cost/latency denial-of-service

Recursive delegation, retries and debates can consume unbounded tokens and tool calls.

**Correction:** every mission/task receives hard budgets:

- maximum delegation depth,
- maximum retries,
- token/model budget,
- wall-clock deadline,
- tool-call budget,
- concurrency limit.

Budget exhaustion is a first-class terminal/blocking state, not a reason to continue indefinitely.

### 9. Generated dependencies are a supply-chain attack surface

Agents can accidentally introduce malicious, abandoned or typo-squatted packages.

**Correction:** dependency policy requires lockfiles, allow/deny checks, vulnerability scanning, provenance where available and review of new production dependencies.

### 10. Observability can leak secrets

Full prompts, tool arguments and traces may contain credentials, personal data or proprietary source.

**Correction:** observability is required, but sensitive fields are classified and redacted before export. Trace storage policy is separate from application logs.

### 11. Model upgrades can silently change company behavior

If provider defaults change, identical missions can behave differently.

**Correction:** every run records:

- model/provider identifier,
- agent definition version,
- prompt/policy version,
- tool/schema versions,
- runtime version,
- relevant configuration.

Reproducibility is semantic, not assumed.

### 12. Autonomous self-improvement can corrupt the evaluator

If the same system changes both its behavior and the tests judging that behavior, it can optimize for the benchmark rather than product quality.

**Correction:** evaluation baselines are protected artifacts. Changes to evals require independent review and cannot be bundled silently with a change whose success they determine.

---

## Final architecture

```text
                         HUMAN OWNER
                              │
                    ┌─────────▼─────────┐
                    │  Approval Gateway │
                    └─────────┬─────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│                     CONTROL PLANE                         │
│ Mission Intake | Planner | Scheduler | Policy | Budgets  │
│ State Machine  | Artifact Registry | Model Router        │
└──────────┬──────────────────┬──────────────────┬──────────┘
           │                  │                  │
     ┌─────▼─────┐      ┌─────▼─────┐      ┌────▼─────┐
     │ Product   │      │Engineering│      │ Assurance│
     │   Pod     │      │    Pod    │      │   Pod    │
     └─────┬─────┘      └─────┬─────┘      └────┬─────┘
           └──────────────────┼──────────────────┘
                              │
                 ┌────────────▼────────────┐
                 │ VERSIONED SHARED STATE │
                 │ Tasks / Artifacts      │
                 │ Decisions / Evidence   │
                 │ Events / Reviews       │
                 └────────────┬────────────┘
                              │
            ┌─────────────────▼─────────────────┐
            │ EVALS + MEMORY + OBSERVABILITY   │
            └───────────────────────────────────┘
```

---

## Seven non-negotiable architecture decisions

1. **Deterministic control around probabilistic workers.** LLMs may propose; policy/state code enforces.
2. **Typed communication over free-form swarm chat.** Canonical decisions are schema-valid objects.
3. **Immutable history, mutable projections.** Current state can change; the event/audit history is never silently rewritten.
4. **Least privilege by capability.** Agents do not inherit broad credentials from the orchestrator.
5. **Evidence beats agent confidence.** Confidence is metadata, never a release gate by itself.
6. **Use multi-agent only when justified.** Specialization and independent checks are tools, not ideology.
7. **Irreversible or externally consequential actions cross a human gate unless an explicit policy has granted a narrower pre-approved envelope.**

---

## Protocol strategy

AI Factory owns an internal protocol first. External standards are adapters, not the core data model.

- **MCP:** preferred adapter family for tools/context providers where useful.
- **A2A:** future adapter for interoperating with external/remote agent systems.
- **Internal typed schemas:** remain canonical so the Factory is not locked to a framework or vendor.

---

## Runtime strategy

Phase 1 starts with a small local runtime and deterministic state machine. Do **not** introduce distributed infrastructure prematurely.

Production evolution should support durable execution semantics: persisted state, resumability, timeouts, retries, idempotent side effects, signals/approvals and replayable audit history. A durable workflow engine may later be adopted behind an abstraction if evaluations justify it.

---

## Final verdict

**GO — WITH ARCHITECTURE REVISION.**

The project is worth building, but the valuable product is not “12 AI agents.” The valuable product is the **operating system that makes replaceable AI workers behave like a reliable software organization**.

The next build step is therefore **Factory DNA + Governance + Autonomy + Threat Model**, followed by the deterministic Control Plane/Orchestrator contract.
