# Real Estate Trust Review — Phase 10-E

**Mission:** `MISSION-001-REAL-ESTATE`  
**Status:** Qualified baseline  
**Purpose:** Preserve suspicious-pattern evidence for independent review without converting anomaly scores into accusations, badges, destructive actions or hidden trust changes.

## Core rule

> An anomaly is a reason to review evidence. It is not a fraud verdict.

The Trust/Fraud slice intentionally separates four concepts:

1. **Observation** — deterministic source facts such as current price disagreement.
2. **Finding** — a typed anomaly artifact that points to those facts.
3. **Review** — an independent operator decision with additional evidence.
4. **Protected trust/action state** — publisher trust, verification badges, listing lifecycle, deletion/suppression and other consequential actions.

A finding can create a review case. It cannot directly cross step 4.

## Baseline detector

`DuplicatePriceDivergenceDetector` is deliberately inspectable and deterministic.

For one canonical listing it:

- loads current duplicate/source members;
- keeps the latest version per `(publisher_id, source_ref)`;
- compares source prices;
- emits no finding below the configured threshold;
- maps inspectable thresholds to `MEDIUM / HIGH / CRITICAL` severity;
- records the affected canonical ID and source-version IDs;
- produces evidence references and a SHA-256 evidence fingerprint;
- creates a deterministic finding ID from detector identity, canonical ID and evidence fingerprint.

The detector has no API for changing publisher trust, verification status or listing state.

## Finding contract

A valid `AnomalyFinding` contains:

- `finding_id`
- `anomaly_type`
- `severity`
- `canonical_id`
- `source_version_ids`
- `detector_id`
- `evidence_refs`
- `evidence_fingerprint`
- human-readable summary
- observed value and threshold

Machine-readable schema: `schemas/real-estate-anomaly-finding.schema.json`.

## Durable review lifecycle

Review cases use an explicit state machine:

```text
OPEN
  ↓
IN_REVIEW
  ├──→ RESOLVED
  └──→ DISMISSED
```

- `OPEN`: anomaly evidence is queued; no protected decision exists.
- `IN_REVIEW`: an identified reviewer has accepted responsibility.
- `RESOLVED`: review concluded as confirmed anomaly or insufficient evidence.
- `DISMISSED`: review concluded as false positive.

Machine-readable schema: `schemas/real-estate-trust-review.schema.json`.

## Independence rule

For `HIGH` and `CRITICAL` findings, the detector identity cannot be the reviewer identity. This prevents the same logical actor from creating a high-impact suspicion and certifying its own interpretation.

## Evidence rule

Resolution requires:

- assigned reviewer identity;
- at least one explicit evidence reference;
- a non-empty review note.

`CONFIRMED_ANOMALY` still means only that the reviewed anomaly is supported. It does **not** mean `FRAUD_CONFIRMED`, `TRUST_REVOKED`, `DELETE_LISTING` or `VERIFICATION_FAILED`.

Any future trust-impact action must use a separate typed action/policy boundary with its own authority and evidence requirements.

## Stale-evidence rule

Before a reviewed finding can be confirmed, `TrustReviewCoordinator` re-runs the detector against current inventory.

If the current evidence fingerprint differs, or the anomaly no longer exists, the previous finding is stale and confirmation is blocked with `StaleFindingError`.

This prevents an operator from resolving a historical suspicion as if the underlying data were still current.

## Audit and restart behavior

`SQLiteTrustReviewStore` persists cases and append-audited review events. Events include:

- actor identity;
- source and target review status;
- outcome when applicable;
- evidence references;
- note;
- timestamp;
- previous event hash;
- current event hash.

The chain can be verified after restart. Mutating an existing event invalidates chain verification.

Queue insertion is idempotent by `finding_id`, so replaying the same detector result does not create duplicate review cases.

## Deliberate non-goals

Phase 10-E does not implement or claim:

- automated fraud verdicts;
- automated publisher punishment;
- trust-badge issuance/revocation;
- listing deletion or suppression from anomaly score alone;
- identity-document verification;
- hidden model-based risk labels;
- production moderation operations.

Those require separate product, policy, legal/security and human-approval design.

## Qualification evidence

Executable qualification is in `tests/test_phase10_trust_review.py` and covers:

- finding generation without domain mutation;
- queue idempotency;
- restart persistence;
- independent reviewer enforcement;
- false-positive safe dismissal;
- evidence-required confirmed anomaly review;
- stale-evidence rejection;
- audit-chain tamper detection;
- presence of machine-readable schemas.
