# Phase 11 — Production Hardening Progress

**Code-side verdict:** `CODE_QUALIFIED`  
**Production verdict:** `NOT_PRODUCTION_READY`  
**Qualified code slices:** multi-mission isolation; verified SQLite backup/restore; secret-reference isolation; verifiable audit archival; durable incident response; deterministic supply-chain/SBOM controls; SLO evidence contracts; representative CI performance regression; deterministic final readiness gate.  
**Remaining blockers:** GitHub branch protection, live production secret-provider qualification, off-site recovery/RPO-RTO evidence, production SLO evidence and other external production infrastructure.

## Qualified evidence

| Slice | Qualified head | GitHub Actions |
|---|---|---|
| Multi-mission isolation | `37036370c224658df458a7677c16ce7d2f081fb5` | `32856981540` success |
| Backup/restore integrity | `1cd3aabbb9efe90ef41cbf04ac84ca046f3ccdfa` | `32861957643` success |
| Secret-reference boundary | `81263dd0ac62b8359e0a2799f88879fbe15f3bc3` | `32868738282` success |
| Audit archival integrity | `cb629f28faac2980dfddb0c7fbcf6953be056b6b` | `32868992458` success |
| Incident-response state machine | `8ba20872100eea33c5fc7380033a0497f269465d` | `32869313829` success |
| Supply-chain/SBOM | `7164da7248e92c76d7596b048d15f7efaebe283c` | `32869793898` success |
| SLO evidence contract | `03487733f3215c5a76a82b403a0a12c29a0d1ac7` | `32870015401` success |
| CI performance regression | `fa5768adb72f4e1fa9aa847a74f287f14ce3adfe` | `32870221506` success |
| Readiness gate/current snapshot | `36dad7240acfb83a349834ae8b816c43a0bf8cdb` | `32870565847` success |

Detailed verdict: `docs/evaluations/PHASE11_CODE_QUALIFIED.md`  
Machine-readable snapshot: `evals/phase11/readiness_current.json`

## 1. Multi-mission isolation

The public scoped runtime prevents artifact, budget and approval state from being read or mutated across mission boundaries. Cross-mission approval access fails closed.

## 2. Verified backup/restore

`factory/runtime/backup.py` uses SQLite online backup, SHA-256 manifests, integrity checks, staged restore and atomic replacement. Tampered/corrupt snapshots cannot replace a healthy destination and overwrite is explicit.

No off-site replication or measured RPO/RTO is claimed.

## 3. Scoped secret references

`factory/runtime/secrets.py` keeps raw credentials outside canonical state. Secret references are mission/capability scoped; cross-mission and missing-capability requests fail before provider resolution; raw material exists only inside the trusted broker→executor boundary. Tracing/evaluation persistence redacts resolved secret material.

No live KMS/Vault/Secrets Manager integration is claimed.

## 4. Verifiable audit archival

`factory/runtime/audit_retention.py` implements archival-before-deletion. Only a contiguous `GENESIS`-anchored ledger prefix can be archived; source integrity is verified first; the archive is SHA-256 bound to a manifest and independently replayed through the ledger verifier. Canonical rows are not deleted.

Destructive audit compaction remains unqualified until archive-anchor recovery/forensics continuity is proven.

## 5. Durable incident response

`factory/runtime/incidents.py` enforces:

`DECLARED → TRIAGED → CONTAINING → CONTAINED → RECOVERING → MONITORING → CLOSED`

with `MONITORING → RECOVERING` allowed. State/evidence/actions survive restart; every mutation is transactionally paired with a hash-chained incident event; protected actions require exact human approval; closure requires recorded recovery evidence; cross-mission access and event-history tampering fail closed.

No real production containment action is claimed.

## 6. Supply-chain/SBOM controls

`factory/reliability/supply_chain.py` AST-scans production imports, rejects undeclared external Python dependencies, requires exact 40-character SHA pins for external GitHub Actions and produces a fingerprinted `AI_FACTORY_SBOM_V1` inventory constrained by `schemas/sbom.schema.json`.

The current `factory/` core has zero external Python runtime dependencies under this scanner. A regression test caught that the first workflow scanner missed YAML `- uses:` syntax; the scanner was corrected and the full suite passed.

## 7. SLO evidence boundary

`factory/reliability/slo.py` defines typed p95 latency, error-rate, throughput and sample-count objectives. Invalid measurements, mixed operations and insufficient samples fail qualification. Local/CI/staging evidence is permanently labeled `NON_PRODUCTION_QUALIFICATION_ONLY`; code raises if it is presented as production-SLO proof.

No production SLO achievement is claimed.

## 8. Representative CI performance regression

`factory/reliability/performance.py` records actual monotonic-clock latency, counts failed calls, fingerprints the execution environment and feeds samples into the SLO evaluator. Current CI qualification measures 100 SQLite Runtime Catalog `latest_artifact` reads after warm-up against a deliberately broad regression sentinel: p95 ≤ 100 ms, zero errors, ≥5 ops/s and ≥100 samples.

This is a regression sentinel, not a production capacity benchmark.

## 9. Deterministic release-readiness gate

`factory/reliability/readiness.py`, `schemas/release-readiness.schema.json` and `evals/phase11/readiness_current.json` now separate code qualification from production readiness.

Mandatory code controls must all be `PASS` with evidence. Missing required controls become `UNVERIFIED`; they are never silently omitted. Mandatory production controls are evaluated independently. The current snapshot deterministically evaluates to:

`CODE_QUALIFIED`

and `assert_production_ready()` raises because production readiness is not proven.

## 10. Verified GitHub governance gap

A direct GitHub branch read reports `main` as **unprotected** and required status-check enforcement as off.

Current control state: `github_branch_protection = FAIL`.

The available GitHub connector exposes protection reads but no branch-protection write action, so this repository-level external control cannot truthfully be enabled from this run.

## 11. Remaining production blockers

The following are intentionally not promoted to PASS:

- `github_branch_protection` — **FAIL**;
- `production_secret_provider` — **UNVERIFIED**;
- `offsite_recovery` — **UNVERIFIED**;
- `production_slo_evidence` — **UNVERIFIED**.

Also not claimed: production deployment, KMS-backed encryption at rest, destructive audit compaction, real incident containment, legal/commercial readiness or real production traffic capacity.

## 12. Next work

The reusable code-side Phase 11 gate is now qualified. Further progress toward `PRODUCTION_READY` requires external/infrastructure evidence rather than more internal claims: enable and verify repository protection, connect a production secret provider through the qualified interface, establish off-site recovery with measured RPO/RTO, and observe real production/staging-to-production SLO evidence behind the required human/account gates.
