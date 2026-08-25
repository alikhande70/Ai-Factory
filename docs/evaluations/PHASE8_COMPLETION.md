# Phase 8 — Organizational Memory & Evaluation System Completion

**Status:** PASS  
**Qualified executable head:** `8e1ac2ceb9359049e38807170fe716d3ab11cf5d`  
**GitHub Actions run:** `32839584595` — success  
**Qualification environment:** Python 3.12, `unittest`, `ResourceWarning` promoted to error.

## What is now enforced

### Organizational memory
- Promotion still requires reviewed evidence and rejects raw `UNTRUSTED_EXTERNAL` sources.
- Durable SQLite memory persists promoted entries across restart.
- Promotion and recall both require the reviewed source hash to match the observed source hash.
- Memory lifecycle changes are append-only audit events linked by a SHA-256 hash chain.
- Existing memory is superseded or deprecated; it is not destructively rewritten.
- Mission-scoped memory cannot be recalled by another mission; global memory has no mission visibility binding.
- Audit-event tampering is detected by chain verification.

### Protected evaluation system
- Regression baselines are immutable by `(baseline_id, version)` and fingerprinted.
- Protected baseline authors/evaluators cannot self-register their own benchmark; registration crosses an independent Control Plane authority.
- An evaluated worker cannot act as its own evaluator.
- Baseline integrity is checked before recording an evaluation run.
- Evaluation runs persist worker/provider identity and baseline fingerprint.
- Metrics include evidence-backed false-completion rate, mean quality, total cost units and mean latency.
- Provider read-model summaries allow evidence-based comparison across recorded runs without changing the baseline.
- Baseline integrity survives process restart.

## Executable qualification scenarios

`tests/test_phase8_memory_eval.py` verifies:
1. promoted memory survives restart;
2. mission visibility is enforced;
3. changed source hashes block promotion and recall;
4. supersession preserves the original record;
5. audit-chain tampering is detected;
6. protected baselines require independent registration;
7. false-completion/quality/cost/latency metrics are calculated from evidence;
8. provider summaries are produced from persisted runs;
9. worker self-evaluation is rejected;
10. mutated protected baselines are rejected.

`tests/test_phase8_eval_restart.py` verifies protected baseline fingerprint integrity after SQLite restart.

## Architecture conclusion

Phase 8 exit criteria are satisfied in the controlled local runtime. The Factory can learn from reviewed outcomes without granting raw agent/web/tool content direct memory authority, and it can evaluate workers/providers without letting the evaluated worker silently rewrite its benchmark or evaluator.

This is not a claim that the current metrics predict real-world model quality universally. Phase 9 must now exercise the complete Factory on a bounded qualification mission and compare it against a simpler baseline to determine whether the control-plane and multi-agent overhead earns its cost.
