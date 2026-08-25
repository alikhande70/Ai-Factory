# Phase 6 — Reliability & Durable Execution Completion

**Status:** PASS (controlled local qualification)  
**Qualified head:** `1c018b6d20777ee80ddc71a9343718c1b380fd87`  
**GitHub Actions run:** `32834489886` — success  
**Scope:** deterministic local reliability semantics; no production deployment or external side effect was performed.

## Qualified capabilities

- A11 DevOps/Reliability role contract exists and remains bounded by Control Plane policy.
- Typed `OperationSpec`, `AttemptRecord`, `RecoveryDecision`, `CircuitBreakerState`, `DeadlineObservation`, `CompensationPlan`, `CompensationRecord` and `ReliabilityMetric` contracts.
- External writes require stable idempotency identity and reconciliation support.
- Unknown external-write outcomes cannot blind-retry; they enter `RECONCILE_REQUIRED`.
- Reconciliation `APPLIED` completes without duplicate action; `NOT_APPLIED` can retry only inside budget; unresolved ambiguity stops safely.
- Retry budgets are finite and deterministic.
- Circuit breaker state is persisted in SQLite and survives process restart.
- Attempt, decision and resulting circuit state are committed in one SQLite transaction so a crash cannot persist an attempt without its associated circuit transition.
- OPEN circuits reject new attempts until an explicit HALF_OPEN probe transition.
- Timeout/deadline observations are derived from the operation contract, persisted, evented and counted.
- Compensation plans must match the operation's declared `compensation_ref`; successful compensation requires an evidence reference.
- Compensation state survives restart.
- Structured reliability counters are durable at mission/operation scope.
- Reliability lifecycle events bridge into the shared runtime tracer under actor `A11-RELIABILITY`.
- Mission-level recovery reconstructs mixed READY/COMPLETE/RETRY/RECONCILE/STOP state entirely from durable canonical records after restart.
- Mission recovery rejects cross-mission operation contamination.
- Release preview requires an exact match between candidate and reviewed fingerprints, assurance `PASS`, and a rollback reference.
- Production release plans remain explicitly human-gated; qualification did not execute a deployment.
- Machine-readable schemas were added for reliability operations and release preview plans.

## Executable evidence added in this phase

- `tests/test_phase6_reliability.py`
- `tests/test_phase6_reliability_persistence.py`
- `tests/test_phase6_durable_extensions.py`
- `tests/test_phase6_mission_recovery.py`
- `tests/test_phase6_tracing_bridge.py`

The latest qualification workflow completed successfully at run `32834489886`; its `unit-tests` job and `Run unit and orchestration tests` step both concluded `success`.

## Important failure mode fixed during implementation

An intermediate design persisted circuit state separately from attempt/decision state. That could have produced a crash window where a failed attempt was durable but the circuit transition was not. The store was revised so attempt, decision, circuit update and their journal events share one immediate SQLite transaction.

## Exit criteria assessment

Phase 6 exit criterion:

> after interruption or ambiguous side-effect outcome, canonical state can be recovered without blind duplicate actions; retry/circuit/rollback rules are deterministic, bounded and auditable.

**Result: satisfied for the controlled local runtime.**

Durability is currently SQLite/local-process qualified. Multi-node durability, production secret handling, real infrastructure deployment and production rollback drills belong to later production-hardening work and are not claimed here.
