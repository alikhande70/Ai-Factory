# ADR-0002 — Interoperability is a boundary, not authority

**Status:** Accepted  
**Date:** 2026-08-25

## Context

AI Factory must interoperate with external tools and independent agents while preserving its deterministic Control Plane, permissions, evidence rules, approval gates and provider independence.

The first supported protocol baselines are:

- MCP `2026-07-28`
- A2A `1.0.0`

MCP and A2A solve different boundary problems and may evolve independently. Their wire formats and SDKs must not become the Factory's canonical internal data model.

## Decision

1. Internal typed contracts remain canonical.
2. MCP and A2A are implemented as pure boundary translators before transport-specific clients are added.
3. Protocol versions are explicit and unsupported versions are rejected rather than silently downgraded.
4. Every discovered external capability declares the Factory capability required to use it.
5. External capability claims are intersected with deterministic Factory policy, budgets and approval state.
6. Endpoint/protocol provenance is retained on requests/results and checked before authorization.
7. External payloads enter as `UNTRUSTED_EXTERNAL`; successful protocol execution does not automatically promote payloads into canonical truth.
8. External writes require stable idempotency identity at the adapter boundary.
9. Ambiguous external outcomes map into Phase 6 reliability semantics. An unknown external-write outcome becomes `RECONCILE`, not a blind retry.
10. `INPUT_REQUIRED` is not interpreted as human approval and cannot bypass the Approval State Manager.
11. Transport I/O, authentication bindings and provider SDKs remain replaceable layers outside canonical semantics.

## Consequences

### Positive

- Provider/protocol SDK replacement does not redesign mission/task state.
- Protocol payloads cannot directly grant permissions.
- Existing reliability, budget and approval controls remain reusable.
- Cross-protocol observability can use common correlation/provenance fields.

### Costs

- Translation code and compatibility tests are required for each supported protocol version.
- Some protocol features may need explicit adapters rather than being exposed automatically.
- New protocol releases require a deliberate compatibility decision.

## Rejected alternatives

### Use MCP/A2A objects directly as canonical state

Rejected because protocol evolution would couple Factory state migrations to external specifications and could let transport metadata leak into authority semantics.

### Accept any protocol version and best-effort parse

Rejected because silent compatibility guesses are unsafe around tools, agents and side effects.

### Trust successful external-agent output automatically

Rejected because execution success is not evidence that the returned content is correct, safe or authorized for canonical promotion.
