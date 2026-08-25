# Phase 7 — Interoperability Completion

**Status:** PASS (controlled transport qualification)  
**Qualified executable head:** `4e5a0310bb873b0c8ef3341c1366658a8d07683a`  
**GitHub Actions run:** `32835211075` — success  
**External network/tool/agent side effects:** none performed

## Qualified capabilities

- Protocol-neutral canonical contracts for external provenance, capabilities, requests, results and authorization decisions.
- MCP boundary pinned to specification version `2026-07-28`; unsupported versions fail closed.
- A2A boundary pinned to released specification version `1.0.0`; unsupported versions fail closed.
- MCP tool discovery and A2A skill discovery translate into the same internal `ExternalCapability` type.
- Discovery can be exercised through a bounded transport abstraction rather than injected directly into canonical state.
- Duplicate capability IDs and malformed discovery descriptors are rejected.
- External endpoint/protocol provenance mismatch is rejected.
- External payloads remain `UNTRUSTED_EXTERNAL` even after a successful protocol result.
- Capability use is intersected with the Factory's deterministic `PolicyEngineV0`, including capability, budget and protected-action approval requirements.
- External-write requests require stable idempotency identity.
- `INPUT_REQUIRED` is represented as input state and cannot be treated as approval.
- Request/correlation identity is preserved across adapter and transport boundaries.
- Malformed MCP/A2A transport results are rejected.
- External protocol results map into Phase 6 reliability semantics.
- Ambiguous external-write outcomes become `RECONCILE`; they cannot blind-retry.
- Failed external results are terminal by default and become retryable only through explicit classification.
- Effect-class mismatch between external capability and durable operation contract is rejected.
- Interoperability request/result lifecycle is visible through the shared runtime tracer.
- Protocol replacement compatibility test proves MCP and A2A translate into the same canonical capability shape rather than changing internal state contracts.
- `InMemoryInteropTransport` provides deterministic discovery/invocation/delegation fixtures without network side effects.
- ADR-0002 records that interoperability is a boundary, not an authority source.

## Executable evidence

- `tests/test_phase7_interoperability.py`
- `tests/test_phase7_policy_reliability.py`
- `tests/test_phase7_gateway.py`
- `tests/test_phase7_discovery_compatibility.py`

Relevant successful GitHub Actions qualification runs:

- `32834779057` — core MCP/A2A guards
- `32834939949` — Policy Engine and Reliability bridge
- `32835211075` — transport discovery and canonical compatibility, including earlier gateway tests in the same repository head history

## Important boundary

This phase qualifies **protocol semantics and controlled transport behavior**, not production network clients. Real authentication, HTTP/gRPC/JSON-RPC transport implementations, remote server certificates, live MCP servers and live A2A agents remain deployment/provider integrations. They must plug into the same `InteropTransport` boundary and cannot bypass policy, provenance or reliability rules.

## Exit criteria assessment

Phase 7 exit criterion:

> supported external tools/agents can be discovered and invoked/delegated through deterministic adapters while unsupported versions, privilege escalation, malformed data and ambiguous side effects are safely rejected or routed into existing reliability/reconciliation mechanisms.

**Result: satisfied for controlled transport qualification.**
