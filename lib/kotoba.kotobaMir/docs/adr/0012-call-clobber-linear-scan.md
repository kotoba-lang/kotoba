# ADR 0012: Call clobbers in the linear scanner

## Status

Accepted. The 2026-08-18 miscompile is **closed by execution**, not by
encodings.

Measured through amu, which runs compiled native code:

| kotoba-mir | what amu saw |
|---|---|
| `8872a54` (before this ADR) | 1094 tests, 0 failures |
| `7f7c556` (scanner takes calls + CFG) | 1096 tests, **62 failures** |
| `7f7c556` + `back-edge?` | 61 failures |
| `ac14016d` (`back-edge?` + drop-backed-at-label) | **native-executor-test + isa-execution-test: 74 tests, 841 assertions, 0 failures** on judah, amu `30370f07` |

The 62 failures were string search (30 AArch64 / 30 x86-64) plus
`let-composes-with-recursion-within-the-fuel-budget`. The one-line
reproducer `(defn main [] (if (string-contains? "abcdef" "def") 1 0))`
returned 0 at `7f7c556` and 1 at `ac14016d`.

This repository's suite and kotoba-native's still do not run a compiled
program. Their green is not this measurement. `:cfg-liveness` is true:
`last-uses` extend live-out across back edges (2026-08-26). Production call+loop uses the scanner
(`:call-live`); leftover pressure still falls back to all-vreg. That is
not a ranking, and it is not a claim that LLVM is beaten.

### The whole suite, and whether `back-edge?` is load-bearing

The measurement above covers the two executing namespaces. On the full suite,
amu `30370f07` is **1096 tests / 8235 assertions / 0 failures across 138 of 138
namespaces**.

**`back-edge?` is not load-bearing for that.** Re-running with the predicate
neutralised gives an identical suite — 1096 / 8235 / 0 — including
`let-composes-with-recursion-within-the-fuel-budget`, the one failure the
predicate had fixed. `drop-backed-at-label` carries every shape amu covers on
its own. The neutralisation was proved live rather than assumed: the overridden
file was made unparseable and the build failed.

The predicate is **not** a routing guard. Iteration 27 ran the full amu
suite with `back-edge?` false: only the four production all-vreg policy
asserts failed. The scanner path already executed (iterations 25–26).
Production call+loop is `:call-live`. Leftover pressure still falls back
to all-vreg via `:spill-required`. `:cfg-liveness` is true.

That corpus: `v3-call-plus-back-edge-is-routed-to-call-live` and amu
`a-call-and-a-back-edge-in-one-function-execute` (n in {0,1,5,50} equals
n, both ISAs). Neutralising `back-edge?` on the iteration-23 fixtures stayed
`[:all-vregs 8]` because those fixtures started with a label:
`entry-argument-plan` throws `:non-prefix-argument`, which is tagged
`:spill-required`. After `lower-phis`, latch last-uses are after their
defs. Arguments as prefix, the scanner completes (`:call-live`)
(`v3-prefix-argument-call-loops-complete-the-scanner`).

## Context

ADR 0006 materializes only values live across a straight-line call. ADR 0011
spills what does not fit, but only on the no-call path. A function that
contained both a call and a label, branch, jump, or phi still took
`allocate-with-spills`: every SSA value received a stack slot. On a 24-live
caller that differed from its straight-line twin by one `if`, that was 99
slots and 325 instructions against 24 slots and 190.

The hardware ABI already restores the preserved tier across a call. The
allocator's on-demand pool (iteration 06) already offers that tier. The
scanner did not use it at a call, so the extra control flow paid all-vreg.

## Decision

The linear scanner accepts calls. The non-leaf pool is scratch then
preserved. Values whose last use follows a call prefer a preserved register
at their definition. Remaining live caller-saved values are stored at their
definition — the store dominates every reload, including an arm that does
not contain the call — then dropped from the assignment. The call uses the
ABI registers. A new result that is itself live across a later call moves
into the preserved tier when a register is free.

Straight-line callers keep the ADR 0006 `allocate-call-live` path. The
linear scanner is the path for control flow. Leftover pressure still fails
into all-vreg.

Physical functions produced this way declare `:call-live`. `:all-vregs`
remains the fallback.

The fallback no longer assigns one frame slot to every SSA definition.
Fixed-point CFG liveness builds a deterministic interference graph, and a
lowest-available greedy coloring lets values in disjoint live ranges reuse a
slot. Lowered phi destinations are treated as definitions on each incoming
edge and as slot uses at the join, so mutually exclusive arms may share while
values simultaneously live around a join or back edge may not. Applying the
fallback in the allocation test to the separately executed call+loop corpus
colors eight SSA definitions into four slots on both target profiles. This
reduces addressable frame footprint; it does not remove spill instructions or
change the scanner's register policy.

`last-uses` records only the highest instruction *index* at which a vreg is
a source. It reads no label and no branch target. Two holes followed from
routing control flow through that:

1. A **back edge** re-reads a value after its textual interval ended.
   `back-edge?` used to send a call-containing function with a backward
   `:mir/jump` or `:mir/branch-zero` to all-vreg. Measured: 62 failures
   became 61. It fixed `let-composes-with-recursion` and did not see
   string search. It is no longer a routing guard; the scanner is.
2. A **then-arm reload** keeps the value in `:assigned` for the else arm,
   which never executed that load and then reads leftover callee-saved
   garbage (`x20`). Store-at-definition does not prevent this. At every
   label after the entry, backed values that are currently assigned are
   dropped so the next use in that block loads them again. Unbacked values
   stay. Rebuilding the free lists on every label, including leaves with
   nothing backed, scrambled phi coalescing; the drop runs only when
   something assigned is backed.

Encoding test: `v3-else-arm-reloads-a-value-the-then-arm-already-reloaded`.
Execution: amu `native-executor-test` and `isa-execution-test` on judah
against native `e8642e0` / mir `ac14016d`.

## Consequences

A caller with one call and one `if` no longer stores every SSA value. Live
across values that fit in the preserved tier do not occupy a slot. Tests
that only count encodings cannot distinguish this implementation from a
wrong one — that is how `7f7c556` shipped. The namespaces that execute
compiled programs are the gate for the next pin, not this repository's
suite.

`:cfg-liveness` is true. Production call+loop uses the scanner
(`:call-live`). A prefix-argument terminating call+loop completes it.
Straight-line ADR 0006 still stores every live-across value. Neither is
withdrawn by closing the miscompile. Leftover pressure still falls back
to all-vreg, whose frame slots are now CFG-live-range colored.
