# ADR 0043: Keep ClojureScript fuel budgets exact

Status: accepted

## Context

The Wasm backend permits a positive fuel budget through `2^62 - 1` and encodes
it as an i64 global initializer. On ClojureScript, `.kotoba` and compiler-policy
i64 values are JavaScript `bigint`s so they remain exact beyond `2^53`.

The fuel validator nevertheless used Clojure's `integer?` predicate and built
`max-fuel` with `bit-shift-left`. Under ClojureScript, `integer?` rejected a
`bigint`, while the shift was a JavaScript int32 operation and silently treated
62 as 30. The JDK-free compiler therefore could not apply an explicitly
declared fuel policy without narrowing it to an unsafe Number.

## Decision

The ClojureScript ceiling is the exact BigInt literal `2^62 - 1`. Fuel accepts
either an ordinary ClojureScript integer or a JavaScript `bigint`; positivity
and ceiling checks remain fail-closed, and the existing BigInt SLEB128 encoder
owns the emitted representation.

The JVM branch retains its existing long-valued ceiling. Amu integration must
exercise the ClojureScript branch and compare policy-bound output with the JVM
backend before advancing this dependency pin.

## Non-claims

This changes no default fuel value, replenishment semantics, charge placement,
or host authority. It only makes the existing declared range exact on both
compiler hosts.
