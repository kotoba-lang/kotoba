# ADR 0006: Materialize only values live across straight-line calls

## Status

Accepted.

## Context

ADR 0005 made scalar direct calls correct by assigning every SSA value a
stable frame slot. That policy stores every definition and reloads every use,
even when most values die before the call. It provides a safe fallback but
inflates frame size, generated code, and memory traffic.

## Decision

For a call-containing function without labels, branches, jumps, or phis, MIR
computes the last use of every SSA value. A value receives a stable slot only
when its definition precedes a call and its last use follows that call.

The allocator keeps ordinary values in the four target allocator registers.
Immediately before a call it materializes each not-yet-backed live-across value
once, schedules the call arguments as a parallel register copy, and treats all
allocator registers as clobbered. Backed values are reloaded lazily at their
next use. One reusable slot is reserved only if an argument-register cycle
requires it.

Physical functions produced by this path declare `:call-live`. The existing
`:all-vregs` policy remains accepted and is selected when register pressure or
control flow prevents the straight-line allocation from completing safely.
Both policies retain the same closed MIR v3 call ABI.

## Consequences

The representative caller frame decreases from four slots to one and performs
one save plus one reload for its single live-across value. A call with no
live-across value needs no spill frame. Multiple calls reuse the value's stable
slot without redundant stores.

This decision does not yet perform CFG liveness or spill-slot coloring. Those
cases continue through the correctness-first allocator and remain explicit in
the function policy.
