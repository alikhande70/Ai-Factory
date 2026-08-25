# AI Factory — Repository Governance Hardening

**Status:** Required before production-grade release governance  
**Scope:** GitHub repository controls that must match the Factory's own evidence/governance philosophy.

## Why this exists

AI Factory's internal architecture enforces bounded authority, evidence gates and protected evaluation. The source repository must not remain materially weaker than the runtime it is intended to build.

Repository settings are external control-plane state. Documentation in this file does not itself prove those settings are enabled.

## Required production hardening

### Protected default branch

The default branch should require:

- pull requests for protected changes,
- required CI status checks,
- branch up-to-date requirement before merge where appropriate,
- restricted force pushes,
- restricted deletion,
- review for governance/security/evaluator changes,
- resolution of review conversations before merge.

### Protected paths

Changes to these areas deserve elevated review:

- `docs/foundation/`
- `docs/governance/`
- `docs/architecture/decisions/`
- `schemas/`
- `factory/control_plane/`
- `factory/reliability/`
- `factory/evaluations/`
- `evals/`
- `.github/workflows/`
- security/approval/policy code anywhere in the repository.

A worker being evaluated must not be the sole authority for modifying its evaluator or protected benchmark.

### Required checks

At minimum:

1. unit tests,
2. orchestration/control-plane tests,
3. schema/contract validation,
4. security/governance regression tests,
5. protected benchmark integrity checks,
6. lint/static checks once the stack stabilizes.

Required checks must be identified by exact workflow/check name in branch rules rather than assumed from documentation.

### Commit/release provenance

Before production hardening is considered complete:

- release commits/tags should use an attributable signing/provenance mechanism where practical,
- build artifacts should record source commit SHA,
- release qualification evidence should bind to an exact commit,
- benchmark reports should bind to exact tested source/version fingerprints.

### Secrets

- no production secrets in repository files, issues, benchmark fixtures or model prompts,
- secret scanning should be enabled where available,
- CI credentials must use minimum scope,
- external system credentials for competitive benchmark adapters must be isolated from benchmark cases and logs.

## Current gap classification

Until external GitHub settings are verified, treat branch protection and required-review enforcement as:

`NOT_VERIFIED_EXTERNALLY`

Do not claim they are active because this document exists.

## Exit criteria

Repository governance is `PASS` only when evidence records:

- actual default-branch protection state,
- required checks and their names,
- review requirements for protected paths or an equivalent enforceable mechanism,
- secret-handling controls,
- release/benchmark provenance policy,
- a negative test or audit showing an unqualified protected change cannot silently become the production release state.
