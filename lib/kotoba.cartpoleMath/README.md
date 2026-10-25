# kotoba-lang/cartpole-math

Safety-first, parameterized cartpole physics written in Kotoba source. The
authoritative implementation is `src/kotoba/cartpole_math.kotoba`; production
artifacts are restricted JavaScript or typed WebAssembly and do not require a
JVM or ClojureScript runtime.

The public bounded-vector ABI exports all four components of one semi-implicit
Euler step (`step-x`, `step-x-dot`, `step-theta`, `step-theta-dot`). Configuration
and state use checked `:vector-f64` values while action/results stay scalar. The
canonical zero-argument exports remain available as reproducible smoke values.

## Test

```sh
kbb -M:test
```

Tests compile the same `.kotoba` source through the reference interpreter,
restricted JavaScript, and typed Wasm. They compare observable f64 results with
a tolerance; Wasm byte-for-byte equality is deliberately not an API contract.
