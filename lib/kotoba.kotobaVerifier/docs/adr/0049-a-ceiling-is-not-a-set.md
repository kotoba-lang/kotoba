# ADR 0049: a ceiling is not a set

Status: accepted. Date: 2026-09-03.

## Context

`max-native-fuel` was `1048576` — 2^20 — and this file has said so since it
learned to check a native artifact's fuel at all. `kotoba.compiler.nbb.cli`
said the same number beside it.

It never bit, and the reason it never bit is worth writing down because it is
the whole shape of the defect.

**The object route does not read the sealed budget.** `package-kernel-object`
picks a per-call tier by symbol name and writes 512 into the artifact's own
context, so the shipped aiueos objects run at 250,000,000 and 2,147,483,647
through a verifier that admits at most 1,048,576 — a factor of two thousand —
and the two numbers never met. The **image** route does read it, so on that
route this was the binding ceiling, and it was two orders of magnitude below
the tiers the object route was shipping.

Meanwhile the number everybody quoted as *the* fuel ceiling was neither of
these. It was 2,147,483,647, and it was the width of the immediate in
`mov qword [r9+8], imm32` (kotoba-native ADR 0078). Three statements of one
subject, at three values, none of them reconciled.

## Decision

**`max-native-fuel` is `kotoba.kir/max-fuel`.** Read, not copied.

That is a departure from this file's standing rule, which its own header
states plainly:

> This verifier rejects by ABSENCE and re-derives its own tables on purpose,
> so a width that reaches `kotoba.compiler.frontend` and `kotoba.kir` and not
> this file is refused here.

The rule is right and it stays. It exists so a producer cannot ratify its own
admitted-operator **set**: if the frontend adds a head and this file imports
the frontend's set, the check becomes a tautology, and rejecting by absence has
a safe direction — refusing something valid is a build failure, admitting
something unchecked is not.

**A ceiling is not a set, and rejecting by absence has no safe direction here.**
A verifier that admits *less* than the interpreter can count refuses valid
artifacts. A verifier that admits *more* ratifies a budget the oracle cannot
decrement — a program that runs forever and returns `:ok`. There is exactly one
right answer and it is a property of the counter, not of the producer. So it is
read from where the counter is.

The counter's exact range is what sets it: `charge!` is `(vswap! fuel dec)` on
a plain host number, which is a double on Node, and measured 2026-09-03,
`x - 1 === x` is already true at 2^53+4. kotoba-kir ADR 0268 carries the
measurement. The value is 9,007,199,254,740,991.

## Consequences

- The image route's ceiling rises from 2^20 to 2^53−1, which is the first time
  a sealed native artifact may declare a budget as large as the object route
  has been shipping.
- The `:over-maximum` case in
  `bounded-native-fuel-is-an-explicit-matched-artifact-contract` is written
  against `(inc ir/max-fuel)` rather than a literal, so a future move of the
  constant cannot leave that assertion testing a number nothing enforces. It
  was `1048577`.
- A new positive half, `a-native-budget-past-the-old-imm32-ceiling-is-admitted`,
  runs the fixture at 2^20, 2^20+1, 2^31, the object probe tier and the ceiling
  itself. Without it the refusal test says only that *some* number is refused,
  which a ceiling of 1 would also satisfy.
- `the-verifiers-ceiling-is-the-interpreters-ceiling` pins both the identity
  and the number, so reading it from elsewhere cannot quietly become reading
  something else.

The kotoba-kir pin advances to `233bd6bb`, which is the commit that exports
`max-fuel`.

## Evidence

`kbb -M:test -n kotoba.verifier-test`: 77 tests, 528 assertions, 0 failures
(run against a `:local/root` kotoba-kir before the pin landed, and against the
pin after).
