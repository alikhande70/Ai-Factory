# Phase 1 Control Plane Contracts

The LLM may propose tasks, assignments and transitions. It may not directly mutate canonical task state. The runtime validates every transition, dependency graph, capability grant and protected action.

## Task transition rules
The state machine lives in `factory/control_plane/state.py`. `DONE` cannot be reached from implementation directly. Normal path: `BACKLOG → READY → IN_PROGRESS → READY_FOR_VERIFICATION → REVIEW → VERIFIED → DONE`.
`REVIEW` requires evidence. `VERIFIED` requires evidence, an independent reviewer and zero unresolved blocking objections. Resuming `AWAITING_HUMAN_APPROVAL` requires an approval record.

## Dependency/write-scope rules
Duplicate IDs, missing dependencies, self-dependencies and cycles are rejected. Tasks may run concurrently only when neither directly depends on the other and declared write scopes are disjoint.

## Capability and budget contracts
Permissions exist as runtime data, not natural-language instructions. Protected capabilities additionally require human approval. Budgets are hard runtime limits and cannot be silently expanded by an agent.

## External side effects
Side-effecting `ActionProposal` objects require an idempotency key plus explicit preconditions and post-action verification. A timeout is an unknown outcome and must be reconciled before retry.
