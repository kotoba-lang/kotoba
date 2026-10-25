# ADR-0064: The carrier needed nothing from this repository

- Status: accepted
- Date: 2026-09-02

## Context

`docs/lang-authority-diff.md` — written by the MEMWIDTH stream, in this
repository, so that it could be reviewed against the encoders it describes —
listed four things the ADR 0285 slice **value** would need, three of them here:

1. `kotoba.native.machine-ir/pilot-expression?` knows one value shape,
   `:scalar`; a slice needs a second, and `value` must return a register
   *pair*.
2. `kotoba.native.x86-64`'s fallback keeps every value in RAX with stack
   pushes; a two-word value needs a second accumulator and a two-slot spill.
3. `kotoba.gmir` / `kotoba.mir` need a two-register SSA value — **or** the
   frontend erases slices into two i64s before KIR.
4. `kotoba.compiler.frontend` needs `[:slice T]` in its type system.

It also named route 3-by-erasure as the cheapest.

## Decision

Route 3 was taken (kotoba-sema ADR 0022), and this ADR records what that cost
here: **nothing**. Not one encoder, table, gate or golden in this repository
moved.

Steps 1 and 2 are not *cheaper by comparison* — they are **unnecessary**.
`pilot-expression?` already answers `:scalar` for a four-operand
`slice-load-u8`, because `kir-kernel-memory-ops` has carried the slice family
since the lowering landed. After erasure there is no two-word value anywhere
below the frontend for a register pair to hold.

## Evidence

- amu ADR 0314: a carried traversal and the same traversal written with
  `(slice-load-u8 base length index)` compile to **identical objects** on both
  `x86_64-aiueos-kernel-v1` and `aarch64-aiueos-kernel-v1`, at all four
  element widths. Crossing the widths differs on both, so the comparison can
  tell two programs apart.
- aiueos ADR 0160: a probe kernel builds a `[:slice :u8]` over a real
  conventional-memory page, passes it as a function parameter, and prints
  `0000082000000410SLC` under q35 + OVMF, exit 33. An overrunning `slice-sub`
  prints nothing at all — this repository's emitted `kernel-subregion` check
  reaches `ud2` before addressing anything.

## Consequences

- `docs/lang-authority-diff.md` §3 is marked superseded in place and gains an
  addendum reading the four steps back against what happened. Its §1 and §2
  still stand as the diff to apply to `kotoba-lang`, with `:slice-carrier`'s
  `:limits` losing `:no-single-value-carrier`.
- **A backend that needs no change for a language feature is a result, not an
  absence of one.** It is recorded here rather than left implicit, because the
  same diff will be read next time someone proposes a value the machine cannot
  hold in one word — and the answer that worked was to stop it reaching the
  machine, not to widen the machine.
- `[:slice :f32]` is still declared and not admitted. There is no
  `slice-load-f32` on either ISA, which is a gap in **this** repository, and
  it is the element type the carrier is ultimately for.
