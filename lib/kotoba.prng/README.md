# kotoba-lang/prng

**Deterministic discrete PRNG that answers the same on every host.**

`(:require [kotoba.prng :as prng])` — zero third-party deps, one `.cljc`
namespace, runs on JVM / ClojureScript / nbb / GraalVM / kotoba-WASM.

## What this is

A 64-bit linear congruential generator (PCG32's default multiplier/increment,
`6364136223846793005` / `1442695040888963407`), seeded once and advanced purely
functionally. The same seed produces the same word stream on the JVM and in
ClojureScript — which is exactly what seeded construction search, test fixtures,
and simulations depend on.

The state is carried through Clojure-style `[value state']` pairs (no mutable
`Random` object):

```clojure
(def s0 (prng/seed-state 42))
(let [[w s1] (prng/word-32 s0)     ; a 32-bit unsigned draw in [0, 2^32)
      [v s2] (prng/next-int s1 256)] ; a bounded draw in [0, 256)
  ...)
```

## What this is NOT

`capability-random-bytes` owns *unpredictable* bytes — atomic authority, safe
random for keys and nonces. This namespace is the opposite: **deterministic and
seeded**, for reproducibility. Never substitute one for the other.

## Portability

`state * 6364136223846793005 + 1442695040888963407` wraps at 2^64. On the JVM
that is primitive `long` unchecked wrap; in ClojureScript a JS double is exact
only to 2^53, so the state is a `goog.math.Long` (bundled with ClojureScript)
doing the same wrapping multiply/add/shift. Both branches run the same
algorithm.

## API

- `(seed-state seed)` — initial 64-bit state from an integer seed.
- `(step-state state)` — advance one step.
- `(word-32 state)` → `[word state']`, `word ∈ [0, 2^32)`.
- `(next-int state bound)` → `[value state']`, `value ∈ [0, bound)`, positive `bound`.

## Build

```
kbb -M:test   # JVM suite
kbb -M:cljs && node target/cljs-verify.js   # ClojureScript portability
```

The shared LCG shape was first proven portable in `com-nvidia-isaac-lab`'s
`shugyo.lcg`; this is that pattern generalised to a kotoba-lang lib and focused
on integer draws.