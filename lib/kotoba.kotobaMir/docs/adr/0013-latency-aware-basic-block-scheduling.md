# ADR 0013: Latency-aware basic-block scheduling

## Decision

Schedule only consecutive SSA segments made from pure, non-trapping integer
operations. All other MIR operations are hard barriers and retain their exact
position relative to surrounding segments.

Scheduling runs after register allocation on physical MIR. Integer segments are
bounded by labels, branches, spills, moves, calls, and every other non-
schedulable operation, so each basic block is scheduled independently once
physical register identities are fixed. Pre-allocation scheduling was
rejected for CFG functions: reordering virtual SSA before the linear scanner
changes register reuse under spill pressure and miscompiles real programs
(`a-value-spilled-in-one-branch-arm-survives-into-the-other` returns 1652
instead of 282 on x86-64). Post-allocation scheduling uses last-definition
physical register dependencies, so reordering cannot change allocation.

Within a segment, a deterministic list scheduler preserves producer-consumer
dependencies. It prefers the longest remaining modeled dependency path, then
the original instruction position. A conceptual issue cycle allows independent
work to fill a modeled multiply dependency gap.

An already-adjacent, single-use AArch64 multiply-add/subtract candidate is also
a barrier pair. The downstream MC selector can fuse it to MADD/MSUB only while
it remains adjacent, so local scheduling must not separate it.

The per-target latency tables are conservative compiler heuristics, not
microarchitecture measurements. This ADR therefore qualifies deterministic
instruction scheduling, but does not claim a runtime speed improvement. Native
execution evidence belongs in the downstream Amu integration.
