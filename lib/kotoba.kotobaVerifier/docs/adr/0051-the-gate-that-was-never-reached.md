# 0051 — the gate that was never reached

Status: accepted
Date: 2026-09-09
Base: `origin/main` `33b3d06`

## Context

`string-operations` admits `string-contains?` and `string-replace-all` on a
stance ADR 0002 states at length: they are target-independent operations whose
contract this verifier always had, and what was missing was only a native
emission.

`string-index-of` is the same shape and was not in the table. It joins it now,
because kotoba-native's `lower-index-of` (its ADR 0081) gives it the native
emission — and gives it out of the SAME scan `string-contains?` already lowers
to. `kotoba$string-find` was already answering the first matching offset; the
predicate folded that offset to 0/1 and this operation returns it. So there is
no new callback, no new value representation, no ABI change, and nothing
ratified here that was not already ratified for `string-contains?`.

## The part worth recording

ADR 0002 said this table is the **second** of two gates, and that opening
either alone unlocks nothing. For `string-index-of` there was a **third**, in
front of both, and it is why this table could not have been tested for the
operation before now: the native backend refuses an unlowered head as

```
aggregate ABI rejected: call-abi-not-admitted
```

because a head with no lowering is call-shaped. Measured 2026-09-09 against
amu `origin/main`, `--target aarch64-macos --jvm-free`: that is the message
`string-index-of` produced, while `string-split-count` — refused by
`kotoba.kir`'s gate instead — produced *"typed values currently require the
kotoba-script web target, typed Wasm target, or qualified native
string/scalar-record/option-i64/result-i64 features"*. Two different refusals
from two different gates, which is how the order was established rather than
assumed.

The arity below is therefore re-derived from the KIR contract
(`kotoba-lang` `lang/guest-grammar.edn`: `(string-index-of haystack needle)`),
not read off a refusal this file had produced. That matters for this file in
particular, whose whole value is that it re-derives its tables rather than
importing anyone's.

## Decision

`string-index-of 2` in `string-operations`.

`verifier_string_search_test.clj` gains it in all three of its shapes: the
admitted arity verifies, the wrong arities are refused **with the arity
message** rather than merely refused — the terminal `runtime KIR operation
rejected` would fire for an absent symbol too, so a test asserting only
"rejected" would pass with this change reverted — and the operands are still
walked.

## Consequences

- A guest may cut a string at a separator on native. That is the practical
  unlock: line-oriented programs need an offset, not a predicate.
- Being stricter than the oracle is sound and being looser is not, so this
  entry is deliberately narrow: one arity, and the operands still verified.
