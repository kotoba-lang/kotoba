# ADR-0022: A guest literal is not a host integer, and this repo now runs on both hosts

- Status: accepted
- Date: 2026-09-02
- Renumbered 0021 -> 0022 on 2026-09-02: two streams took 0021 the same
  day. This one merged first (`3d7a6f0` 03:11Z) and
  `0021-open-the-second-gate-for-the-interrupt-entry-address.md` second, so
  by first-come this file should have kept the number -- it moves instead
  because it is the one whose downstream references (amu ADR-0292, amu
  `deps.edn`, amu `aggregate_abi_test.clj`) had not landed yet and could
  still be corrected in the same breath. Numbering is a discovery alias;
  a dangling reference is a real defect.

## Context

`verify-expr!` gates the i64 and i32 shift forms on their count being an
integer LITERAL in `[0,63]` / `[0,31]`. The restriction is load-bearing: it is
the only reason the native backends may lower these onto `CL` / `x1` with no
range check, since the hardware truncates a larger count modulo the width
exactly where `kotoba.kir`'s evaluator traps.

Both gates were spelled with bare `integer?`, under a comment arguing that
`integer?` "is the right predicate on both runtimes here" because "a count in
`[0,63]` is small enough that no bigint representation question arises."

That argument is about the VALUE. The predicate tests the REPRESENTATION. On
nbb every `.kotoba` integer literal is a JavaScript `bigint` whatever its
magnitude -- `kotoba.compiler.kotoba-reader` reads every integer token as one
(`:cljs (js/BigInt token)`) and `kotoba.kir` coerces every literal to one
before it enters the runtime value stream -- and cljs `integer?` does not
recognize a bigint (`(integer? (js/BigInt 4))` => false, confirmed live). So
on the JDK-free route the count of every shift failed the literal test:

```
$ amu compile probe.kotoba --target x86_64 --jvm-free --output probe.o
{:format :kotoba.cli-error/v1, :ok false, :error :verify,
 :diagnostic {:code :kotoba/verification-failed, :source "probe.kotoba"},
 :message "runtime KIR i64 shift count rejected"}          # exit 65
```

for `(defn shl [x] (i64-shift-left x 4))`, which the JVM route compiled to a
2213-byte object with `:ok true`. No artifact using an i64 or i32 shift could
be built without a JDK. The measured effect on the caller was worse than a
crash: the refusal named the count, and the count was a perfectly good
literal, so it read as "your program is wrong".

Every other guest-literal site in this file already carried the correct
reader-conditional guard -- `admitted-native-fuel?`, `valid-effect?`,
`lowered-cost`, `verify-expr!`'s own literal arm, both `cap-call` ids, the
artifact effect check -- each re-spelling the same nine-form expression
inline. The two shift sites were the ones where someone reasoned about it
instead and got a different answer.

The reason nobody saw it: this repository's only test entry was
`kbb -M:test`. A verifier whose entire value is re-deriving a rule
independently of the producer was being exercised on one of the two hosts that
run it.

## Decision

1. One named predicate, `guest-integer?`, holds the rule "this is a
   `.kotoba` integer literal as it reaches this verifier on this host":
   `integer?` on `:clj`, `(or bigint-value? integer?)` on `:cljs`. Both shift
   gates use it. The seven sites that had already open-coded the same
   conditional now call it too, so a new guest-literal site has a name to
   reach for rather than a choice to re-make.

   Range comparisons stay outside the predicate: JS relational operators
   compare bigint against number directly, so `(<= 0 n 63)` is exact on both
   hosts once `n` is known to be one of the two admitted representations.

2. `run-tests.cljk` runs the portable slice on nbb, alongside the JVM suite.
   Its namespaces must be `.cljc`.

Fail-closed is unchanged. A non-literal or out-of-range count still reaches
the same refusal, with the same reason literal, on both hosts.

## Consequences

- `test/kotoba/verifier_shift_literal_test.cljk` builds the count through
  `guest-int`, which is `(long n)` on `:clj` and `(js/BigInt n)` on `:cljs` --
  the representation the running host's reader actually produces. This is the
  whole reason the cljs half can go red: a quoted `4` written in a test file is
  read by the HOST's reader as a plain cljs number, passes bare `integer?`, and
  would have been a test that could never fail.
- Its `rejection` helper re-throws anything that is not a `:phase :verify`
  refusal. A negative case that goes red for some other reason has not
  demonstrated the gate, and must not be counted as if it had.
- Break-checked in both directions, on both hosts.
  Restoring bare `integer?`: nbb red on the admission cases with
  `runtime KIR i64 shift count rejected`, JVM green -- which is the defect,
  reproduced by the test. Weakening the predicate to `some?`: both hosts red
  on the non-literal cases, JVM through the `ClassCastException` that the
  literal test is what prevents.
- Counts: JVM `kbb -M:test` 71 tests / 420 assertions, nbb
  `run-tests.cljk` 8 tests / 91 assertions, 0 failures on both.
- Not addressed here: the other direction of the same asymmetry. The JVM suite
  covers 71 tests and the nbb entry covers 1 namespace. Every remaining
  `.clj`-only test is a rule this repository has never checked on the host
  that the JDK-free route uses.
