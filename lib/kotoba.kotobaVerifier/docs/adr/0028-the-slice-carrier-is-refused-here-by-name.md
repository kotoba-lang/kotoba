# ADR-0028: The slice carrier is refused here by name

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-sema ADR 0009 admits `[:slice T]` as a **source** type and erases it
into two i64 words before HIR. This verifier already refused one — a slice is
not in `native-word-field-types`, not a scalar record, not a variant, not a
`[:ref ...]`, so `native-boundary-type?` said no. But it said no the way it
says no to `[:banana :u8]`: by absence, surfacing as

```
runtime KIR function shape rejected {:function p}
```

which is true and tells a caller nothing. That is the right default for a
shape no source can write; it is the wrong answer for one a source can write
and a pass is supposed to have removed.

## Decision

`erased-source-carrier-types` names the heads that a source syntax admits and
a lowering deliberately does not carry:

```clojure
{:slice :kotoba.error/slice-not-a-native-boundary-type}
```

A function whose `:param-types` or `:result` carries one is refused before the
shape check, with the function, the type and the reason in the `ex-data`.

The map is an **independent copy** of `kotoba.kir/native-erased-source-carrier-types`,
not an import, for the reason ADR 0024 gives: the verifier re-derives what
native admits, because being stricter than the oracle is sound and being looser
is not. `kotoba.verifier-kir-agreement-test` now compares two lists rather than
one — the native float admission list and this one — and names the difference
in each direction.

`nil` from `erased-source-carrier-refusal` is not admission. Refusal by absence
stays the default.

## Evidence

- A `[:slice :u8]` parameter and a `[:slice :u8]` result each produce
  `:kotoba.error/slice-not-a-native-boundary-type` with the type attached, and
  the message names a source carrier type.
- The **erased** program — the same function with `base`/`length` as separate
  `:i64` parameters and `(slice-load-u8 base length index)` in the body —
  passes the same gate. Without that control, a verifier that refused
  everything would satisfy the two assertions above.
- Red: with `erased-source-carrier-types` emptied, 8 of 50 assertions fail —
  the refusal falls back to `runtime KIR function shape rejected`, and the
  agreement check reports `kotoba.kir has (:slice) and the verifier has ()`
  plus `SCANNED 0 verifier carrier heads` at the evidence floor.
- Suite at the advanced kotoba-native pin: 88 tests / 622 assertions, 0
  failures; nbb 8 / 91, 0 failures.

## Consequences

- Every slice head already reaches this verifier: `slice-{load,store}-u{8,16,32,64}`
  have been in `kernel-memory-operations` here since MEMWIDTH, and the carrier
  compiles to exactly those. What this adds is the refusal for the shape that
  must never arrive.
- The kotoba-kir pin advances to `061283e9` to reach the list this test
  compares against.
