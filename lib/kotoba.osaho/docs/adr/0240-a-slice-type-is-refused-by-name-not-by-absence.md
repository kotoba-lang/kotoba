# ADR-0240: A slice type is refused by name, not by absence

- Status: accepted
- Date: 2026-09-02

## Context

`native-word-value-type?` is a gate, and a gate's right default is to refuse
everything it has not been told about. `[:slice :u8]` fell to that default:
it hit the `case`'s `false` arm, the module was rejected, and the caller
printed *"typed values currently require the kotoba-script web target, typed
Wasm/CLJS target, or the qualified native one-word ... slice"* — a paragraph
that names neither the type nor the reason.

That is fine for `[:banana :u8]`, which no source program can write. It is
not fine for `[:slice T]`, which kotoba-sema's source syntax **admits** as a
parameter type and erases into two `:i64` parameters before emitting HIR
(kotoba-sema ADR 0009). If that erasure ever failed to run, the only symptom
would be a refusal about typed values in general.

## Decision

Two additions, both data-shaped:

```clojure
(def native-erased-source-carrier-types
  {:slice :kotoba.error/slice-not-a-native-boundary-type})

(defn native-boundary-type-refusal [type] ...)      ; the reason, or nil
(defn native-unadmitted-boundary-types [hir] ...)   ; {:function :type :reason}*
```

`native-word-value-type?` gains an explicit `:slice false` arm carrying the
reason in a comment, so the refusal reads as a decision rather than an
omission.

`nil` from `native-boundary-type-refusal` does **not** mean admitted. It means
"no named reason", which stays the default for every shape a source program
cannot write. This is a list of the shapes a lowering deliberately does not
carry, not a second admission table.

## Consequences

- A failure to erase is reported with `:kotoba.error/slice-not-a-native-boundary-type`
  and the function and type it was found on. amu puts that in the refusal's
  `ex-data`; the message string is unchanged, so nothing that pins it moves.
- `native-erased-source-carrier-types` is data for the same reason
  `native-floating-point-operations` is (ADR 0236): kotoba-verifier keeps its
  own copy of this refusal and the two can be compared instead of drifting.
- **The oracle needed no change for the carrier itself.** The carrier's
  semantics are the `slice-{load,store}-u{8,16,32,64}` family this repository
  has evaluated since MEMWIDTH, and `kotoba.kir-slice-carrier-test` now
  executes a full carried traversal against a real `:memory` image — a sum of
  eight bytes, the trap at `index == length` at all four element widths, and a
  `kernel-subregion` narrowing that traps on its own shorter length rather
  than the parent's. That is the ADR 0285 carrier running, not being read.
