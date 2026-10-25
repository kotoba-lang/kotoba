# kotoba-lang/math

**Floating-point and elementary math that answers the same on every host.**

`(:require [kotoba.math :as m])` — zero third-party deps, one `.cljc`
namespace, runs on JVM / ClojureScript / nbb / GraalVM / kotoba-WASM.

## Why this exists

Measured 2026-08-20 across the compiler stack: **50 `Math/*` references, and
nothing owning the surface.** The frequency ranking shaped this namespace
rather than a wish to mirror `java.lang.Math`:

```
abs 14 · PI 8 · nextUp 4 · exp/log/pow 3 · ceil/floor/min/max/sqrt/rint 2
       · sin/nextDown/atan2 1
```

## The three that justify a library rather than a reader conditional

JavaScript has no equivalent of `nextUp`, `nextDown` or `rint`. Without a
shared implementation each cljs call site hand-rolls IEEE-754 bit
manipulation — and **a hand-rolled `nextUp` that is subtly wrong still returns
a plausible double.**

`rint` is the sharper trap. `js/Math.round` is *not* it: round-half-to-even
gives `2` for `2.5` and `0` for `0.5`, while `Math.round` gives `3` and `1`. A
rounding-mode difference survives every round-trip test and then changes a
content-addressed digest.

The suite is built to catch exactly that: replacing `rint`'s cljs branch with
`js/Math.round` takes nbb to **2 failures and exit 1**.

## Surface

```clojure
m/PI  m/E

(m/abs x) (m/ceil x) (m/floor x) (m/sqrt x) (m/exp x) (m/log x)
(m/sin x) (m/cos x) (m/pow x y) (m/atan2 y x) (m/min x y) (m/max x y)

(m/rint x)       ; nearest integral double, ties to EVEN
(m/next-up x)    ; least double strictly greater  (IEEE-754 nextUp)
(m/next-down x)  ; greatest double strictly less  (IEEE-754 nextDown)
```

Everything operates on host doubles. There is no wrapper type: these are used
inside numeric loops where a box per operation would be paid on every one.

## Verify

```sh
kbb -M:test                                      # JVM
npx nbb@1.4.210 --classpath src:test run-tests.cljk  # ClojureScript
```

Both run the **same** `.cljc` suite: `4 tests, 25 assertions, 0 failures`.
