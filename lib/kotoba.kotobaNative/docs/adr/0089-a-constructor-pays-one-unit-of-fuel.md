# ADR 0089: a constructor pays one unit of fuel

Status: accepted. Date: 2026-09-30.

## Context

amu ADR 0353 point 7 moves allocation into the one 64-bit fuel ledger:
kotoba.kir (osaho 635bea6d) debits one unit at every constructor in
`cell-constructor-ops`, before it evaluates the operands, and restricted ESM
and wasm32 followed (kotoba-script 58d75dae, kotoba-wasm 7ff9ad0d). Native
fuel was the entry prefix of a re-entering function plus the counted loop's
bulk pre-charge, and no constructor paid anything. Measured under amu's
`tools/kexe_loader.c` with `KEXE_FUEL`, on both ISAs: a loop building 1,000
records answered under 1002 units, the same budget as the loop that builds
nothing; a 100-cell cons list under 506; 300 vector literals, which
`vector-region` keeps in locals, under 102.

## Decision

`machine-ir/charge-constructors` rewrites every constructor of the program's
own functions, `(C args)` to `(do (fuel-charge!) (C args))`. It runs in both
`emit-program`s after `vector-region` and before the string-search,
string-index and document augmentation, so one source constructor costs one
unit however it is lowered: `string-index-assoc` is one unit, not the two
`vector-conj` it may become. `vector-region` charges the literals it keeps in
locals itself, as a binding in front of their items.

`fuel-charge!` lowers to the kotoba-gmir runtime operation `:fuel-charge`
(arity 0), which kotoba-mir addresses at 8 -- the context's fuel word, not a
host slot. Both encoders emit it inline as the entry prefix's own bytes with
the instruction's own label: `dec qword [r9+8] / jns / inc / ud2` and
`ldr / subs / b.hs / brk / str`. Exhaustion leaves the counter at 0, so the
loader reports `budget/fuel` as it does for the entry charge. No context
version moves; no host is asked anything.

The charge is not a re-entry: `function-reenters-guest?` ignores it, so a
constructing leaf gains no entry charge. It is not pure either: kotoba-mir's
bulk-fuel allow-list does not admit a runtime call, so a counted loop that
constructs keeps its per-step charge and the bulk pre-charge is left to loops
that build nothing.

`charges-written` marks KIR whose charges are already written out, for tests
that compare a form with its hand-written lowering: a `record-new` costs one
unit and the pair chain it lowers to one per pair, so the hand-written form
has to carry the source's charge rather than its own.

## Consequences

Measured after, on both ISAs: 2002, 707 and 402 -- the price of allocating is
the reference's (1,000, 201 and 300 units); one unit short, `budget/fuel`.
A 400-step counted loop costs 402 without records and 802 with them.
amu's `native-constructors-charge-fuel-test` pins it.

Every program that constructs moves bytes; a program that does not is
byte-identical. kotoba-verifier re-derives an artifact by re-emitting it
through this repository, so it follows with no change of its own.
