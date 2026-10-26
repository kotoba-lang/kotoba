# ADR 0236: The native float admission list is data, so two repositories can compare it

## Status

Accepted.

## Decision

The five floating-point sets that `only-native-word-typed-features?` branches
on are now named public vars —
`native-f64-arithmetic-operations`, `native-f32-arithmetic-operations`,
`native-float-width-conversions`, `native-f64-comparison-operations`,
`native-f32-comparison-operations` — plus their union,
`native-floating-point-operations`. The admission arm reads those vars; they
are not a parallel description of it.

`kotoba-verifier` keeps deciding for itself. Its own arms stay inline and it
does not require this namespace at runtime. What changes is that its **test**
requires it and asserts the two sets are equal, naming every differing head.

## Why not just have the verifier read this list

Because the verifier's independence is the property that makes it a verifier.
Its own comment says it: being stricter than the oracle is sound, being looser
is not. If it imported the admitted set, an operation admitted here would be
admitted there by construction, and re-verification would stop being a second
opinion.

But independence is not the same as *unobserved divergence*, and until now the
two lists had no relation at all — they were two literal sets in two repos,
kept equal by whoever last remembered both. That failure mode has a shape:

- admitted here, absent there → `amu check` is green and `amu compile
  --jvm-free` fails with `:error :verify`, after every other layer has already
  accepted the program;
- absent here, admitted there → the stricter side wins, which is safe, but the
  verifier is now checking a language nobody can write.

The first of those actually happened on 2026-09-02: the f32 arm was missing
from the verifier, and it was found by compiling the f32 dot-product example,
not by any check. SYSOPS hit the same wall the same day from the other
direction.

A test is the right instrument. It runs in the repository that must not
diverge, it reads the other repository's value across the dependency edge it
already has, and it cannot make the verifier looser — the worst it can do is
fail.

## Evidence

`kbb -M:test -n kotoba.kir-test`.

The agreement check itself lives in kotoba-verifier
(`kotoba.verifier-kir-agreement-test`) with its red/green shown there: removing
one head from either side names that head and fails.
