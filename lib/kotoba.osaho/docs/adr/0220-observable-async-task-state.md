# ADR 0220: The resource table owns observable task state

Status: accepted

## Context

An affine task handle may be returned to guest code while a provider still has
work in flight. Previously `task-fulfill!` returned a new same-ID map, but
`task-poll` read state from whichever map the caller held. The guest's original
pending handle therefore could not observe host completion. Describing that as
an async provider contract would be incorrect.

## Decision

The linear resource table is authoritative for task liveness, state, and ready
stream. `task-poll`, `task-cancel!`, `task-drop!`, and all fulfillment variants
resolve the current entry by handle ID. Returned maps remain compatible
snapshots, but they no longer own evolving task state.

Fulfillment registers one bounded stream and atomically changes the task entry
from pending to ready. A rejected duplicate or racing fulfillment drops the
new stream so no unreachable affine resource remains. Dropping any same-ID task
snapshot also drops the currently attached stream.

## Consequences

- A provider may retain a task handle, complete it later, and guest polling of
  the original handle observes readiness.
- Copies do not duplicate authority: liveness and state remain keyed by one ID.
- Use-after-drop, double completion, and completion after cancellation fail
  closed.
- This is the reference JVM/CLJS ownership plane. Component resource-table
  lowering remains a distinct physical backend concern.
