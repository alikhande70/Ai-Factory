# Phase 11 — Production Hardening Progress

**Status:** In progress  
**Qualified slices:** multi-mission isolation; verified SQLite backup/restore; scoped secret-reference handling; verifiable non-destructive audit archival; durable incident response; deterministic supply-chain/SBOM controls; deterministic SLO evidence contracts  
**Not yet complete:** representative scale/performance qualification, production SLO observation, repository protection enforcement, external production infrastructure qualification.

## 1. Multi-mission isolation

The shared runtime catalog is wrapped by mission-scoped access so artifact, budget and approval state cannot be read or mutated across mission boundaries through the public scoped API. Cross-mission approval lookup/decision fails closed.

Qualified head: `37036370c224658df458a7677c16ce7d2f081fb5`  
GitHub Actions run: `32856981540` — **success**.

## 2. Verified SQLite backup/restore

Phase 11 includes `factory/runtime/backup.py` and `schemas/backup-manifest.schema.json`.

Implemented guarantees include SQLite online backup, SHA-256 binding, source/staged integrity checks, tamper rejection, atomic replacement and explicit overwrite. A corrupt snapshot cannot replace a healthy destination.

Qualified test head: `1cd3aabbb9efe90ef41cbf04ac84ca046f3ccdfa`  
GitHub Actions run: `32861957643` — **success**.

## 3. Scoped secret-reference handling

Phase 11 includes `factory/runtime/secrets.py` and `schemas/secret-reference.schema.json`.

Implemented guarantees:

- Canonical state holds opaque `SecretReference` metadata, never resolved credential values.
- References are mission-, provider-, purpose- and capability-bound.
- Cross-mission or missing-capability access fails before provider resolution.
- The provider contract exposes resolution only; enumeration is not part of the interface.
- Raw values exist only inside the trusted broker → executor boundary.
- `SecretMaterial` has non-revealing display semantics.
- Structured tracing and evaluation serialization redact secret material before persistence.

Qualified test head: `81263dd0ac62b8359e0a2799f88879fbe15f3bc3`  
GitHub Actions run: `32868738282` — **success**.

This does not claim integration with a live production KMS/Vault/Secrets Manager.

## 4. Verifiable audit archival

Phase 11 includes `factory/runtime/audit_retention.py` and `schemas/audit-archive-manifest.schema.json`.

Retention is implemented first as **archival, not deletion**. The source ledger is integrity-verified; only a contiguous `GENESIS`-anchored prefix can be archived; archive bytes are SHA-256 bound to a manifest; archived events are independently replayed through the original ledger verifier. Non-monotonic timestamps and archive/manifest tampering fail closed. Canonical audit rows are not deleted by this slice.

Qualified test head: `cb629f28faac2980dfddb0c7fbcf6953be056b6b`  
GitHub Actions run: `32868992458` — **success**.

Destructive audit compaction remains unqualified until an archived-anchor/recovery protocol proves replay, provenance and incident-forensics continuity across the hot/archive boundary.

## 5. Durable incident response

Phase 11 includes `factory/runtime/incidents.py` and `schemas/incident-record.schema.json`.

The incident lifecycle is deterministic:

`DECLARED → TRIAGED → CONTAINING → CONTAINED → RECOVERING → MONITORING → CLOSED`

with an allowed `MONITORING → RECOVERING` regression when recovery is not stable.

Implemented guarantees:

- incident identity, severity, mission and affected resources are explicit;
- state, evidence and action records survive restart;
- each incident mutation is paired with a per-incident hash-chained event in the same SQLite transaction;
- no incident/evidence/history delete API exists;
- protected containment/recovery actions require an exact approved proposal from the mission-scoped runtime approval catalog;
- cross-mission incident access fails closed;
- closure requires recorded evidence and explicit recovery verification;
- event-history mutation is detected.

A qualification-flow mistake was found during implementation and corrected before qualification: the first test attempted the `MONITORING` transition inside an expected-failure block and then attempted it a second time. The test was corrected to prove the actual invariant—monitoring may begin, but closure is rejected until recovery evidence is independently recorded and verified.

Qualified test head: `8ba20872100eea33c5fc7380033a0497f269465d`  
GitHub Actions run: `32869313829` — **success**.

This does not execute real production containment actions; such actions remain behind policy/human gates.

## 6. Deterministic supply-chain inventory and SBOM controls

Phase 11 includes `factory/reliability/supply_chain.py` and `schemas/sbom.schema.json`.

Implemented controls:

- production `factory/` Python imports are AST-scanned and classified as standard-library, internal or external;
- any undeclared external Python dependency fails qualification;
- currently the production Factory core has **zero external Python runtime dependencies** under this scanner;
- GitHub Actions references are required to use exact 40-character commit SHAs rather than floating tags;
- the current workflow pins `actions/checkout` and `actions/setup-python` to exact verified commits;
- a deterministic `AI_FACTORY_SBOM_V1` inventory records external Python dependencies and CI action pins;
- SBOM content is SHA-256 fingerprinted and tamper-verifiable;
- a machine-readable schema constrains the SBOM format.

A real regression was found by the new test suite: the first workflow scanner recognized `uses:` only when it was not written as a YAML list item, so a valid `- uses: actions/checkout@v4` line could escape the pin check. The scanner was corrected to handle both YAML forms, and the repository-wide suite then passed.

Qualified head: `7164da7248e92c76d7596b048d15f7efaebe283c`  
GitHub Actions run: `32869793898` — **success**.

The pinned action revisions work in the current CI environment, but action-runtime maintenance remains ongoing; a SHA pin provides immutability, not permanent support guarantees.

## 7. Deterministic SLO evidence contracts

Phase 11 includes `factory/reliability/slo.py` and `schemas/slo-evidence.schema.json`.

Implemented guarantees:

- a typed SLO declares an operation, maximum p95 latency, maximum error rate, minimum throughput and minimum sample count;
- invalid/NaN latency and invalid durations fail closed;
- observations from a different operation cannot be mixed into an objective;
- p95 uses a deterministic nearest-rank calculation;
- insufficient sample sets cannot qualify even if their measured latency looks good;
- error budget is calculated explicitly and may become negative when the budget is exceeded;
- evidence records its environment (`LOCAL`, `CI`, `STAGING`, `PRODUCTION`);
- local/CI/staging evidence is permanently marked `NON_PRODUCTION_QUALIFICATION_ONLY` and raises if code attempts to present it as production-SLO proof;
- production evidence may only be claimed when both the environment is explicitly production and the complete objective qualifies.

Qualified head: `03487733f3215c5a76a82b403a0a12c29a0d1ac7`  
GitHub Actions run: `32870015401` — **success**.

This slice qualifies the **measurement/claim boundary**, not production performance. No production SLO achievement is claimed.

## 8. Repository-governance verification

A direct GitHub branch read on the current repository still reports `main` as **unprotected** and required status-check enforcement as off. This is now verified external state rather than an assumption.

Current classification: `GITHUB_MAIN_PROTECTION = NOT_ENABLED`.

The available connector in this build exposes branch-protection reads but not a branch-protection write action, so this run cannot truthfully claim to enable the repository rule. The software/CI side is prepared for exact required checks, but GitHub account-level enforcement remains an external governance task.

## 9. Boundaries not yet claimed

Production hardening still does **not** claim:

- off-site backup/archive replication,
- KMS-backed encryption at rest,
- automated disaster-recovery orchestration or measured RPO/RTO,
- live production secret-provider integration,
- destructive audit compaction,
- real production incident execution,
- representative high-load/scale qualification,
- production SLO compliance,
- GitHub branch/review protection enforcement,
- production deployment.

External infrastructure/account actions remain subject to policy and human approval where required.

## 10. Next recommended hardening slice

Add a **representative local/CI scale qualification harness** for the deterministic core: multi-mission catalog isolation, append-only ledger throughput, artifact persistence/reload and Mission 001 canonical search. Persist environment fingerprint + operation counts + latency samples, feed them into the SLO evidence contract as non-production evidence, and keep thresholds broad enough to detect regressions without pretending CI timing is a production capacity benchmark.
