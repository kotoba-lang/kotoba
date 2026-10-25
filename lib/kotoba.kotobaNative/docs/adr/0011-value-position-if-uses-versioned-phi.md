# ADR 0011: Value-position `if` uses versioned phi

## Status

Accepted.

## Context

Tail `if` can return directly from each branch, but an `if` nested inside
arithmetic, a binding, a condition, or a non-final `do` must produce one value
after control flow rejoins. The legacy emitter handled these forms; the
production machine-IR path deliberately rejected them because GMIR v1 had no
merge-value contract.

Writing both branch results to one virtual register would violate MIR's
single-definition invariant. Evaluating both branches and selecting afterward
would be semantically wrong because an unselected branch may trap.

## Decision

Value-position scalar `if` lowers to GMIR v2:

1. evaluate the condition once;
2. branch to explicit then/else blocks;
3. lower only the runtime-selected branch;
4. route each branch through a unique exit block and explicit jump;
5. join with one canonical phi whose incoming records name those exits;
6. let MIR lower the phi to dedicated merge storage before allocation.

Programs without phi remain GMIR/MIR v1. Malformed `if`, non-scalar branches,
critical-edge phi, and unsupported operations continue to fail closed.

## Consequences

Nested value `if`, `let` bindings containing `if`, `if` conditions containing
`if`, and non-final `do` control now use the complete production path on x86-64
and AArch64. The first implementation pays one bounded frame slot per scalar
phi; later coalescing is an optimization, not a correctness dependency.
