# ADR-0053 — The ask is filed, and the receipt points at it

Date: 2026-08-18

## Status

Accepted. The blocking gap is now a request someone can answer:
[kotoba-lang/amu#625](https://github.com/kotoba-lang/amu/issues/625). The
ratchet still reads ten, and will until that issue moves.

## What was verified before filing

ADR-0052 named `kernel-compare-exchange-u32` as the form holding four of the
ten. Filing a wrong issue is worse than filing none, so the claim was checked
against the compiler rather than inferred from its error message:

- **`compare-exchange` occurs nowhere** in the pinned compiler tree
  (`1e21a1f5…`), and nowhere in the current `kotoba-lang/amu` checkout
  (`29e8386`) either. Neither does
  `kernel-value-runtime-capability-table` or `kernel-publish-current-domain`.
- **The siblings that work do occur**: `kernel-load-u8-4k` and
  `kernel-store-u8-4k` are in amu's own `aiueos_target_test.clj`, and the same
  objects call them and get past them — the rejection lands on a later form.
- **amu had no issue about it** (`gh issue list --search compare-exchange`,
  empty), and its open issues are exactly this shape (#611: "native targets
  reject a module that has both a shift and a `:bool` parameter").

So the three forms are not spelling variants of admitted intrinsics: **the
family these objects were written against is larger than the one that exists.**
Two checks that could have made this the wrong issue — a newer amu having it,
and a duplicate already open — were run and came back negative.

The atomic is the load-bearing one for a reason worth stating: the arena's
design is a u32 lock word at offset 0 of a single RW/NX page, with everything
else mutated only while it is held. Without compare-exchange there is no lock,
so those four objects **cannot be expressed**, rather than being expressed
awkwardly.

## Decision

**The receipt names where the work is.** `:value-runtime/upstream` maps each
refused form to the issue that asks for it, and
`every-refused-form-points-at-where-the-work-is` fails when a form has no
entry.

A rejected form with no upstream reference is work nobody has asked for. The
receipt would name a wall and point at no one, which is how a measurement
becomes a complaint — and it is the state this repository was in for three
iterations, holding ten red assertions that described a compiler nobody had
told.

## Executable evidence

`aiueos.value-runtime-baseline-test`: **10 tests, 71 assertions, 0 failures**
(was 9/68). Full suite **624 tests, 9368 assertions, 19 failures** — the
baseline nineteen. Lint unchanged.

**Both directions, shown**: dropping one form's upstream entry fails only
`every-refused-form-points-at-where-the-work-is`, with the edit asserted to
have applied first.

## Remaining boundary

- **Nothing is fixed here and nothing can be.** Four of the ten need an
  intrinsic this repository does not own. The honest state is: measured,
  classified, asked.
- **The three export-symbol failures are not filed.** They are a different
  question — whether the contracts or the target selection is wrong — and
  issue #625 says so rather than bundling them.
- **The intermittent twentieth suite failure is still unexplained**
  (ADR-0051).
- **No answer is guaranteed.** Filing is not fixing, and a receipt pointing at
  an open issue is still a receipt with ten failures in it.
