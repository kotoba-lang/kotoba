# ADR 0238 — `bit-or` beside a typed value

Status: accepted
Date: 2026-09-02

## What was measured

`only-native-word-typed-features?` refused `bit-or` and `bit-not`. Both are
i64 word operations that the frontend, this file's evaluator and both native
backends already emit — `bit-or` since ADR-2607254600 D2 — and neither
introduces a value representation the one-word slice does not have. They are in
`non-string-typed-ops` because they were **added to the arithmetic surface
after that set was written**, and nothing gave them an admitting case in the
walk.

The refusal was invisible for as long as it existed, and the reason is worth
writing down rather than the fix:

- amu's `compile-native!` consults this predicate **only when the module is
  `:kotoba.hir/v3`**, and a module becomes v3 only by using a typed value.
- So an object could use `bit-or` freely — aiueos
  `os/aiueos/kotoba/qwen35-gguf-kv-scan.kotoba` does, sixty times — as long as
  nothing beside it was typed, and an object could use f32 freely.
- **The first object to use both was refused.** It was a port of
  `fp16_to_f32` (aiueos `kernel/qwen35_quant.c:87`), whose three `|`s are the
  whole of what it does, and the message was `typed values currently require
  the kotoba-script web target, typed Wasm target, or qualified native
  string/scalar-record/option-i64/result-i64 features` — a sentence about typed
  values that names neither operation and points at the half that was fine.

Measured 2026-09-02 against amu `25907a65`, kotoba-kir `6b459e2`.

## Decision

Admit `bit-or` and `bit-not` in the walk, beside `bool-not`, which sits there
for the same reason and was measured the same way.

## What is NOT widened, and why the boundary is not a principle

The refused set, measured op by op on 2026-09-02:

| refused | admitted |
|---|---|
| `i64-shift-left` `i64-shift-right` `u64-shift-right` `xorshift32` | `i32-shift-left` `i32-shift-right` `u32-shift-right` `i32-wrap` `u32-wrap` `i32-xor` `i32-wrapping-add` `i32-wrapping-mul` `bit-and` `bit-xor` `quot` |

**The i32 shifts are admitted and their i64 twins are not.** They carry the
same operand restriction — the count must be an integer literal in range, which
is what lets a backend lower them onto CL without emitting a mask — so the
asymmetry measures the omission as *arbitrary rather than principled*. That is
a reason to widen the i64 three deliberately, with their own evidence, and not
a reason to widen them as a side effect of this increment. They stay refused
here and the table above is pinned in the test so the asymmetry cannot be
mistaken for a decision.

## Evidence

`test/kotoba/kir_bit_or_typed_admission_test.cljk`, 4 tests / 19 assertions.
Both directions, and shown red: deleting the new case fails
`bit-or-and-bit-not-are-admitted-beside-a-typed-value` on all three bodies,
including the `sign | exponent | mantissa` shape that found it.
`kir-f32-native-admission-test` and `kir-admission-let-binding-test` unchanged:
27 tests / 266 assertions together, 0 failures.
