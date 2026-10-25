# ADR 0024: Two repositories may disagree, but not quietly

## Status

Accepted.

## Decision

`kotoba.verifier` keeps re-deriving the native floating-point admission set
independently of `kotoba.kir`. What changes is that a test now compares the two
and fails naming every head only one side has.

The two arms' heads and arities move out of `verify-expr!` into
`#'kotoba.verifier/f64-operations` and `#'kotoba.verifier/f32-operations` so the
test can read the values the code actually branches on. The kotoba-kir pin moves
to `6b459e2`, the commit that exports
`kotoba.kir/native-floating-point-operations`.

## Why not import the list and be done

Because the independence is the property that makes this a verifier. Its own
note at the f32 arm says it: being stricter than the oracle is sound, being
looser is not. If this namespace imported the admitted set, an operation
admitted there would be admitted here **by construction**, and re-verification
would stop being a second opinion. The pin is a comparison, not a source.

## Why a check was needed anyway

Independence is not the same as unobserved divergence, and until now the two
lists had no relation at all — two literal sets in two repositories, kept equal
by whoever last remembered both. The failure has a shape and a cost:

- **admitted by kir, refused here** → `amu check` is green, `amu compile
  --jvm-free` fails with `:error :verify` after every other layer has accepted
  the program. This is what happened on 2026-09-02: the f32 arm was missing
  entirely and was found by compiling the f32 dot-product example, not by any
  check. ADR 0023 is that repair.
- **accepted here, not admitted by kir** → the stricter side wins, which is
  safe, but this repository is now checking a language nobody can write, and
  nothing says so.

Both directions are reported, in those words, because an `=` that fails printing
two thirty-six-element sets does not say which head moved.

## Shown red before it was believed

Removing `f64-min` from this repository's own arm:

```
native float admission drift -- admitted by kotoba.kir and REFUSED by the
verifier: f64-min (this shape compiles green and fails at verify time)
```

Removing `f32-add` from kir's exported set instead:

```
native float admission drift -- accepted by the verifier and NOT admitted by
kotoba.kir: f32-add (the verifier is checking a language nobody can write)
```

Restored, green. The reporting function is additionally exercised against
synthetic sets in both directions, so the assertion about the message does not
depend on today's contents.

There is an evidence floor: two empty sets are equal and say nothing, so the
test also asserts both sides have at least thirty heads, and names members whose
absence is a decision (`f32-min`, `f32-max`, the `-checked` and truncating
float↔int conversions) and members whose presence is (`f64-min`, `f64-max`,
`f32-add`, `f32-unordered`, `i64-to-f32-rounded`).

## Note on `f32-min` / `f32-max`

The comment in the f32 arm gave x86's `MINSS`/`MAXSS` NaN behaviour as the
reason those two stay out, and said the f64 arm "already admits that
disagreement". It did, measurably — six wrong answers in the eighteen
NaN/signed-zero rows executed under Rosetta on 2026-09-02, with AArch64 right on
all twenty-four of its observations — and kotoba-native has repaired it
(`x86-f64-min-max`). The corrected sequence carries over to binary32 unchanged,
so what is missing is an admission through seven repositories, not an encoding.
The comment now says that. Nothing about the verifier's behaviour changes.

## Evidence

`kbb -M:test`, whole suite, at the bumped pin.
`kbb -M:test -n kotoba.verifier-kir-agreement-test`: 3 tests, 37 assertions.
