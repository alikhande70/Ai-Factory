# AI Factory — Initial Threat Model

**Status:** Foundation baseline. This document must evolve with the runtime.

## Protected assets

- source code and project artifacts,
- user/project private data,
- credentials and secrets,
- canonical project state,
- approval decisions,
- agent/tool permissions,
- evaluation baselines,
- audit history,
- deployment/account resources,
- model/tool budgets.

## Trust boundaries

Treat all of the following as separate trust zones:

1. human input,
2. retrieved web/document/email/external content,
3. LLM output,
4. agent scratch state,
5. canonical state,
6. local sandbox/workspace,
7. tool adapters/MCP servers,
8. external APIs/accounts,
9. CI/CD and production environments,
10. observability/tracing storage.

Crossing a boundary requires validation appropriate to the data/action.

---

## Primary threats

### T01 — Direct or indirect prompt injection
Untrusted content attempts to redefine company policy, reveal secrets, invoke tools or alter goals.

Controls:
- retrieved content is data, not authority,
- instructions and data are separated structurally,
- tool authorization is deterministic,
- sensitive operations require policy/approval,
- adversarial prompt-injection evals.

### T02 — Excessive agency / tool abuse
An agent has unnecessary tools or broad credentials and performs harmful unintended actions.

Controls:
- capability-scoped permissions,
- task-bound tool allowlists,
- short-lived credentials where possible,
- downstream authorization independent of LLM decisions,
- human gates for consequential actions.

### T03 — Memory poisoning
Malicious or incorrect material is persisted and influences future work.

Controls:
- scratch/canonical/organizational memory separation,
- schema validation,
- provenance,
- promotion review,
- versioning and rollback,
- no automatic promotion of retrieved content.

### T04 — Insecure inter-agent communication
A compromised or mistaken agent sends instructions that another worker accepts as authority.

Controls:
- typed signed/attributed messages,
- authorization evaluated at receiving boundary,
- no privilege delegation through plain text,
- canonical event ledger,
- source identity and task scope on every message.

### T05 — Cascading multi-agent failure
One false assumption propagates through dependent agents and becomes consensus.

Controls:
- evidence references,
- independent review,
- deterministic tests,
- explicit assumption fields,
- dependency-aware invalidation when upstream artifacts change.

### T06 — Human approval manipulation
Attacker-controlled content causes misleading approval descriptions.

Controls:
- system-rendered approval UI from structured payload,
- exact target/action/cost/scope displayed separately from model explanation,
- approval bound to proposal hash,
- changed proposal invalidates previous approval.

### T07 — Cost/loop denial of service
Recursive delegation, retries or oversized context causes runaway compute/API cost.

Controls:
- hard budgets,
- delegation-depth limits,
- concurrency limits,
- retry ceilings,
- circuit breakers,
- per-mission cost telemetry.

### T08 — Duplicate side effects after retry
A timeout causes a successful external write to be repeated.

Controls:
- idempotency keys,
- optimistic concurrency/version preconditions,
- action reconciliation,
- postcondition verification,
- explicit side-effect classification.

### T09 — Supply-chain compromise
Generated code imports malicious, vulnerable or unmaintained dependencies/actions/images.

Controls:
- lockfiles,
- dependency review for production additions,
- vulnerability/license scanning,
- pinned CI actions/images where practical,
- SBOM/provenance in production release pipeline.

### T10 — Secret exfiltration through prompts/logs/tools
Credentials leak to model context, traces, artifacts or external tools.

Controls:
- secrets never stored in prompts/repository,
- secret references instead of values,
- output/log redaction,
- scoped environment injection,
- egress-aware tools,
- secret scanning in CI.

### T11 — Evaluation gaming
Agent modifies or weakens tests/evals to make its own implementation pass.

Controls:
- evaluation changes reviewed independently,
- protected baseline suites,
- hidden/adversarial cases where appropriate,
- implementation and evaluator ownership separation.

### T12 — Correlated reviewer failure
Multiple reviewers repeat the same model assumptions.

Controls:
- context isolation,
- deterministic verification first,
- model/config diversity for high-risk review when justified,
- adversarial role objectives,
- evidence rather than majority vote.

### T13 — Workspace collision / conflicting parallel edits
Parallel agents overwrite or invalidate each other's changes.

Controls:
- isolated branches/worktrees/sandboxes,
- declared artifact/file ownership per task,
- conflict detection before integration,
- merge/rebase validation,
- dependency graph scheduling.

### T14 — Stale-state execution
An agent acts on a decision or artifact that has been superseded.

Controls:
- artifact versions/hashes,
- task input version pinning,
- precondition checks before write/action,
- invalidation events.

### T15 — Rogue or compromised external agent/tool
A third-party tool/agent lies about capability or returns malicious instructions/data.

Controls:
- external agents/tools are untrusted principals,
- capability negotiation does not imply trust,
- explicit allowlists and scopes,
- sandboxing,
- policy mediation on every external side effect.

---

## Security invariants

1. Natural language never grants privilege.
2. A model never receives a secret merely because it asks for it.
3. Retrieved content never outranks company policy.
4. Human approval applies only to the exact structured proposal approved.
5. Critical state changes are attributable and auditable.
6. Retrying a side effect requires an idempotency/reconciliation strategy.
7. Security gates cannot be disabled by the implementation being evaluated.

---

## Initial security test families

- indirect prompt injection through documents/web/tool output,
- cross-agent spoofing,
- memory poisoning and rollback,
- unauthorized tool request,
- privilege escalation,
- approval-dialog manipulation,
- recursive delegation runaway,
- duplicate side-effect retry,
- secret leakage through logs/traces,
- malicious dependency proposal,
- stale artifact execution,
- evaluator tampering.

These become executable evals as the runtime is implemented.
