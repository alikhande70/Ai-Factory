# Phase 11 — Production Hardening Progress

**Status:** In progress  
**Qualified slices:** multi-mission runtime isolation; verified SQLite backup/restore; scoped secret-reference handling  
**Not yet complete:** audit retention policy/enforcement, incident response, dependency/SBOM controls, scale/performance qualification, production SLOs, repository protection verification.

## 1. Multi-mission isolation

The shared runtime catalog is wrapped by mission-scoped access so artifact, budget and approval state cannot be read or mutated across mission boundaries through the public scoped API. Cross-mission approval lookup/decision fails closed.

Qualified head: `37036370c224658df458a7677c16ce7d2f081fb5`  
GitHub Actions run: `32856981540` — success.

## 2. Verified SQLite backup/restore

Phase 11 includes `factory/runtime/backup.py` with a deterministic backup boundary for canonical SQLite state.

### Implemented guarantees

- Uses SQLite's online backup API instead of copying a live database file, so committed WAL-backed state is captured consistently.
- Every backup gets a machine-readable manifest with format version, timestamp, source name, byte size, SQLite integrity result and SHA-256 digest.
- Backup creation runs `PRAGMA integrity_check` and refuses to qualify a corrupt snapshot.
- Backup and manifest are not overwritten unless explicitly requested.
- Restore validates manifest shape/version, exact byte size, exact SHA-256 and SQLite integrity before touching the destination.
- Restore is staged into a temporary database, integrity-checked again, then atomically replaces the destination.
- A corrupt/tampered backup fails before replacement; an existing healthy destination is preserved.
- Replacing an existing destination requires explicit `overwrite=True`.

Machine-readable contract: `schemas/backup-manifest.schema.json`.

### Executable verification

`tests/test_phase11_backup_restore.py` covers:

1. complete recovery of mission-scoped artifact, budget and approval state,
2. rejection of a tampered backup while preserving an existing destination,
3. explicit overwrite requirement,
4. manifest tamper rejection,
5. prevention of accidental snapshot overwrite.

Qualified test head: `1cd3aabbb9efe90ef41cbf04ac84ca046f3ccdfa`  
GitHub Actions run: `32861957643` — **success**.

## 3. Scoped secret-reference handling

Phase 11 now includes `factory/runtime/secrets.py` and `schemas/secret-reference.schema.json`.

### Implemented guarantees

- Canonical configuration holds opaque `SecretReference` metadata, never a resolved credential value.
- Every reference is bound to an explicit mission, provider, purpose and required capability.
- Cross-mission access and missing-capability access fail **before** the secret provider is called.
- The provider contract deliberately has no list/enumerate operation.
- Raw material is resolved only inside the trusted `SecretBroker` and is injected only into a trusted executor callback for the requested binding.
- `SecretMaterial` has non-revealing `str`/`repr` semantics.
- Structured tracing redacts `SecretMaterial` and common credential-bearing keys before persistence.
- Evaluation serialization passes through the same secret-safe projection boundary.
- Secret-reference schema contains no field capable of carrying a raw value.

### Executable verification

`tests/test_phase11_secret_references.py` covers scoped injection, cross-mission denial, capability denial, non-enumerability, display redaction, trace redaction, evaluation redaction and schema value exclusion.

Qualified test head: `81263dd0ac62b8359e0a2799f88879fbe15f3bc3`  
GitHub Actions run: `32868738282` — **success**.

### Important boundary

This does **not** claim integration with a production KMS/Vault/Secrets Manager. The current implementation establishes the provider-neutral security contract and uses a fake provider only in tests. Production provider connection remains an external/infrastructure action and must preserve the same mission/capability boundary.

## 4. Backup/secret boundaries not yet claimed

The current hardening does **not** yet claim:

- off-site backup replication,
- KMS-backed encryption at rest,
- production retention schedules,
- automated disaster-recovery orchestration,
- RPO/RTO compliance,
- restoration of external systems outside the SQLite runtime database,
- live production secret-provider integration.

Those require separate qualification and, where external accounts or credentials are involved, the appropriate policy/human gates.

## 5. Next recommended hardening slice

Implement **audit retention as verifiable archival, not destructive deletion**: define a retention policy, export a contiguous append-only ledger prefix to a hash-bound machine-readable archive, verify the archive independently, and do not compact/delete canonical audit history until recovery and provenance rules for archived anchors are separately proven.
