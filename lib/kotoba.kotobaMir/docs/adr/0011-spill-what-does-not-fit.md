# ADR 0011: Spill what does not fit

## Status

Accepted.

## Context

ADR 0006 and the on-demand pool (iteration 06) still failed whole when live
values exceeded the registers on offer. `allocate-without-spills` rejected
`:spill-required`, and `allocate-with-spills` then gave every SSA value its
own stack slot. A body needing twelve live values on x86-64 fell as far as
one needing five used to: all of memory, or none of it.

The pool size is not the same on both ISAs (eleven on x86-64, nineteen on
AArch64), so there is now a workload on each side of that cliff.

## Decision

The linear allocator spills only the live value with the furthest next use,
and only after the free list, a dying left operand, and the reserve tier
are empty. A body that already fits never reaches that step, so its
assignment stays byte-for-byte what it was.

Calls that cannot complete the straight-line call-live path still take
all-vreg. This decision does not colour spill slots or compute CFG liveness.

## Consequences

Under the scratch tier alone, the six-live exhaustion body uses two slots
instead of eleven. One past the full pool uses one slot instead of
`pool+1`. Both sides of the cliff now have a test that turns red if the
fallback returns.
