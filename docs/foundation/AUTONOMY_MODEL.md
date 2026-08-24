# AI Factory — Autonomy Model

Autonomy is a permission level earned by evidence, not a personality trait.

## Core rule

A worker may reason broadly but act only inside a narrow capability envelope.

## Levels

### L0 — Advisory
Can analyze, propose and review. No repository or external mutations.

### L1 — Sandboxed creation
Can create artifacts in an isolated workspace. Cannot merge, deploy or use protected credentials.

### L2 — Scoped repository execution
Can modify assigned files/branch, run approved local tools/tests and create reviewable commits.

Requirements:
- explicit task contract,
- resource scope,
- tool allowlist,
- budget,
- acceptance criteria.

### L3 — Controlled integration
Can perform bounded integration actions after required verification gates, such as updating an integration branch or running CI workflows.

Cannot self-approve protected actions.

### L4 — Pre-approved external automation
Can execute specific reversible external actions only inside a policy envelope previously authorized by the owner.

Example structure:

```yaml
capability: deploy_preview
resource: mission-014-preview
max_cost_usd: 0
production: false
expires_at: 2026-09-01T00:00:00Z
```

Anything outside the envelope returns `AWAITING_HUMAN_APPROVAL`.

### L5 — High-trust production automation
Reserved for mature, repeatedly evaluated workflows. Even at L5, legal/financial/identity-bound or explicitly protected actions may still require direct human approval.

L5 is not a project-launch target.

---

## Autonomy is per capability, not per agent

An agent does not receive a universal level.

Example:

```yaml
agent: A11-DEVOPS
capabilities:
  read_ci_logs: L3
  deploy_preview: L3
  deploy_production: L0
  rotate_production_secret: L0
```

This prevents role names from becoming blanket privilege grants.

---

## Autonomy promotion

A capability may be promoted only after measurable evaluation across representative missions.

Promotion evidence should include:

- success rate,
- false completion rate,
- rollback/incident rate,
- security findings,
- human intervention frequency,
- budget compliance,
- regression performance.

Promotion requires explicit policy change. A model cannot promote itself.

---

## Autonomy downgrade

Automatic downgrade may be triggered by:

- critical security failure,
- repeated unsupported completion claims,
- budget runaway,
- permission boundary violation,
- corrupted/missing evidence,
- abnormal tool behavior,
- model/provider behavior change detected by evals.

A downgraded capability requires review before restoration.

---

## Execution budgets

Every run receives explicit limits.

```yaml
budget:
  max_model_calls: 30
  max_tool_calls: 80
  max_delegation_depth: 3
  max_retries_per_step: 2
  max_parallel_workers: 4
  max_wall_clock_seconds: 3600
  max_cost_usd: 2.00
```

Budgets are enforced by runtime code. Agents may request an extension but cannot grant it to themselves.

---

## Side-effect classes

### PURE
Read/compute only. Safe to retry.

### IDEMPOTENT_WRITE
Write can safely repeat when using an idempotency key/version precondition.

### REVERSIBLE_SIDE_EFFECT
External mutation with a verified rollback/compensation path.

### IRREVERSIBLE_SIDE_EFFECT
Destructive, public, financial, identity-bound or otherwise consequential. Human gate required unless an exact protected policy says otherwise.

The task contract must declare the side-effect class before execution.

---

## Human escalation

Agents should not ask the user trivial engineering questions that can be resolved from requirements, repository state, research or safe defaults.

Escalate when:

- requirements contain a material business contradiction,
- a protected irreversible choice is required,
- authority/account access is missing,
- legal/eligibility acceptance is required,
- two viable options have materially different owner-facing consequences,
- the system cannot proceed safely after its bounded investigation/retry policy.

The goal is **low-friction autonomy, not zero-human governance**.
