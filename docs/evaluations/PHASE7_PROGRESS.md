# Phase 7 — Interoperability Progress

**Status:** IN PROGRESS  
**Latest executable qualification head:** `c9b645abfea9ea9c0ca3620c83c6adb5178a0e36`  
**GitHub Actions run:** `32834939949` — success

## Qualified so far

- Protocol-neutral typed contracts for external provenance, capabilities, requests, results and authorization decisions.
- External content defaults to `UNTRUSTED_EXTERNAL`.
- MCP adapter is explicitly pinned to `2026-07-28`; unsupported versions are rejected.
- A2A adapter is explicitly pinned to `1.0.0`; unsupported versions are rejected.
- MCP tool and A2A skill discovery translate into the same internal `ExternalCapability` contract.
- External endpoint/protocol provenance mismatch is rejected.
- External capabilities cannot expand Factory capabilities; capability intersection is deterministic.
- `InteropPolicyGuard` connects external capability use to the existing `PolicyEngineV0`, including budget and protected-action human approval checks.
- External-write MCP/A2A requests require an idempotency key before a request object can be built.
- Request/correlation identifiers survive result translation.
- `INPUT_REQUIRED` remains external input state and is never interpreted as human approval.
- `InteropReliabilityBridge` maps external results into Phase 6 attempt/recovery semantics.
- Ambiguous external-write result maps to `UNKNOWN` and deterministically yields `RECONCILE`, not retry.
- Failed external result is terminal by default and becomes retryable only when the caller explicitly classifies it retryable.
- Effect-class mismatch between discovered external capability and durable operation contract is rejected.
- Machine-readable schemas added for external capability and external task request.
- Architecture decision recorded in `ADR-0002-interoperability-boundary.md`.

## Executable evidence

- `tests/test_phase7_interoperability.py`
- `tests/test_phase7_policy_reliability.py`

GitHub Actions runs:
- `32834779057` — success for core MCP/A2A adapter guards.
- `32834939949` — success for deterministic Policy Engine and Reliability bridge qualification.

## Remaining before Phase 7 PASS

- Concrete transport/client fixtures that simulate discovery and invocation/delegation through a bounded transport abstraction rather than only pure translation.
- Trace/redaction integration for external request/result lifecycle.
- Schema/result fixtures for malformed payload rejection at the boundary.
- A bounded compatibility fixture proving MCP/A2A adapter replacement does not mutate canonical internal contracts.
- Final Phase 7 completion report and CI evidence.

No external tool call, remote agent delegation or production side effect was executed by this qualification.
