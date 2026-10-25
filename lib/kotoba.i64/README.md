# kotoba-lang/i64

**Signed 64-bit integer semantics that do not change with the host.**

`(:require [kotoba.i64 :as i64])` — zero third-party deps, one `.cljc`
namespace, runs on JVM / ClojureScript / nbb / GraalVM / kotoba-WASM.

## Why this exists

Every consumer of this workspace's compiler stack needs the same three things
— the range boundaries, two's-complement wraparound, and predicates that
actually recognise a 64-bit value — and until now each reached for the host to
get them.

Measured 2026-08-20 across `amu`, `kotoba-kir`, `kotoba-native` and
`kotoba-wasm`:

| host primitive | references | repositories |
|---|---|---|
| `Long/MIN_VALUE` / `Long/MAX_VALUE` | 79 | 4 |
| `js/BigInt` | 187 | 4 |

One semantics, four repositories, two spellings. That is a missing library
rather than a style preference — and it is the concrete reason those
repositories' suites only run on the JVM.

## The representation differs by host, deliberately

On the JVM a value is a primitive `long`; on ClojureScript it is a JS
`bigint`. Neither is wrapped in a record, because the hot paths here are
arithmetic and a box per operation would be paid on every one. What this
library guarantees is that the **operations agree**: same inputs, same value,
and `->string` produces the same text.

## `clojure.core`'s predicates are not safe on the cljs side

This is the single most important reason the namespace exists rather than
being a pair of constants. Confirmed live:

```clojure
(clojure.core/zero? (js/BigInt 0))   ;=> false     ← a wrong answer, not an error
(clojure.core/bit-shift-right big 1) ;=> throws "Cannot mix BigInt and other types"
```

A wrong answer that looks plausible cannot be left for the caller to notice,
so `i64/zero?`, `i64/neg?`, `i64/pos?` and the bitwise operations are provided
here and the core ones are excluded from the namespace.

## Surface

```clojure
i64/min-i64  i64/max-i64  i64/zero  i64/one

(i64/i64? x)        (i64/->i64 x)      (i64/in-range? x)
(i64/zero? x)       (i64/neg? x)       (i64/pos? x)
(i64/wrap x)                            ; two's complement into 64 bits
(i64/add x y)       (i64/sub x y)       (i64/mul x y)     (i64/negate x)
(i64/bit-not x)     (i64/bit-and x y)   (i64/bit-or x y)  (i64/bit-xor x y)
(i64/shl x n)       (i64/ashr x n)      (i64/lshr x n)
(i64/->string x)                        ; identical text on every host
```

**Shift counts are refused, not masked.** The JVM masks a shift count modulo
64 silently, so `(shl x 64)` is a no-op there and something else elsewhere; a
disagreement that returns a plausible number is the worst kind, so an
out-of-range count throws on both hosts.

**`->string` rather than `str`.** cljs renders a bigint with a trailing `n` in
some contexts, and that difference has reached content-addressed output
before.

## Provenance

Promoted from `kotoba.kir.cljs-i64`, which had the ClojureScript half of this
and no JVM half, so nothing outside `kotoba-kir` could use it. The docstrings
recording *why* each cljs branch is shaped the way it is (the floor-division
`ashr`, the `BigInt.asIntN` wrap) come from that implementation and are kept.

## Verify

```sh
kbb -M:test                                    # JVM
npx nbb@1.4.210 --classpath src:test run-tests.cljk  # ClojureScript
```

Both run the **same** `.cljc` suite. A 64-bit library checked only on the JVM
is checked on the host that already had the semantics for free — every defect
this library prevents lives on the other side.

Measured at v0.1.0, both runtimes: `8 tests, 30 assertions, 0 failures`.
Verified to discriminate: breaking `wrap`'s cljs branch takes nbb to
`4 failures` and exit 1.
