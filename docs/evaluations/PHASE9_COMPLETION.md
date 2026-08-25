# Phase 9 — Factory Qualification Mission Completion

**Status:** PASS (controlled qualification)  
**Qualified executable head:** `c07a5d443adc03507dee83d324b01a700ea34aab`  
**GitHub Actions run:** `32840227411` — success  
**Qualification fixture:** controlled booking workflow; no production side effect.

## Question answered

Phase 9 did not ask whether the Factory has more features than a simple worker. It asked whether the additional control-plane/multi-role complexity can earn its cost on a mission where safety, persistence, review and recovery matter.

The qualification compared two paths under the same protected dimensions:

- **Factory path:** executes the controlled full-stack outcome with mission intake, design traceability, migration, independent assurance evidence, isolated engineering workspaces, reconciliation semantics, protected approval, restart persistence and reviewed organizational-memory promotion.
- **Simple path:** executes the same user-visible booking happy path and schema migration directly, without the additional control layers.

## Protected dimensions

The Factory path is required to provide evidence for all 11 dimensions:

1. mission planning,
2. architecture/UX traceability,
3. full-stack behavior,
4. migration behavior,
5. security review,
6. QA/regression coverage,
7. parallel isolation,
8. retry/reconciliation safety,
9. approval gating,
10. persistence/replay,
11. reviewed memory promotion.

A qualification run is rejected if any Factory dimension is missing.

## Controlled comparison result

The result is intentionally evidence-derived rather than manually scored:

- Factory evidence coverage: **11/11 (1.0 quality proxy)**.
- Simple-path evidence coverage: **2/11 (~0.182 quality proxy)**.
- Factory false-completion rate for this protected case bundle: **0.0**.
- Simple path, when claiming the complete protected mission after only its happy-path/migration evidence: **1.0 false-completion proxy**.
- Controlled cost proxy: **11 evidence units vs 2 evidence units**. This is an execution-complexity proxy, not provider billing cost.
- Wall-clock latency is measured for both paths at runtime and persisted into the protected evaluation store. It is environment-dependent and is not used as a fixed pass threshold.

This qualification therefore demonstrates a real tradeoff: the Factory costs more work and normally more orchestration, but for a mission requiring the protected dimensions it prevents a happy-path implementation from being mistaken for a complete, release-ready system.

## Important routing conclusion

The result does **not** mean every task should use the full Factory path.

`QualificationEvaluator` explicitly rejects complexity with no outcome gain. If a Factory path does not improve false-completion/correctness or achieve a material quality improvement, the result says to preserve the **single-worker fast path**.

Therefore the evidence supports the architecture decision made in the original audit:

> multi-agent/control-plane execution is justified by measurable value, not by agent count.

## Executable evidence

`tests/test_phase9_bounded_qualification.py` exercises or carries audited same-run evidence for:

- validated mission intake,
- Phase 3 design traceability,
- real frontend → backend → SQLite booking roundtrip,
- idempotent SQLite schema migration,
- blocking HIGH security finding contract,
- QA acceptance coverage,
- non-overlapping Frontend/Backend workspaces,
- ambiguous external write → `RECONCILE`,
- protected action `PENDING` before explicit approval,
- artifact recovery after runtime restart,
- independently reviewed memory promotion and recall,
- protected evaluation baseline registration,
- Factory and simple path evaluation persistence,
- false-completion/quality/cost/latency read-model metrics.

`tests/test_phase9_qualification_framework.py` separately proves that:

- missing required evidence prevents qualification,
- measurable safety/quality gain can justify overhead,
- more complexity cannot win when it fails to improve outcomes.

## Scope limitation

This is a deterministic controlled qualification, not evidence that every external model/provider, production deployment, or arbitrary software mission will achieve the same result. Phase 10 can now use the qualified Factory on a real domain mission; Phase 11 must later harden multi-mission isolation, secrets, backup/restore, incident response, scale and production SLOs before a production-ready claim.
