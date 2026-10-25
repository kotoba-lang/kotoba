# kotoba-lang/reader

**One reader for the `.kotoba` grammar, on both runtimes.**

`(:require [kotoba.reader :as r])` — zero third-party deps, one `.cljc`
namespace, runs on JVM / ClojureScript / nbb / GraalVM / kotoba-WASM.

## Why this exists

The workspace carried **two readers for one grammar**: `clojure.tools.reader`
(a JVM-only Maven library) on the JVM, and a purpose-built ClojureScript
reader inside `kotoba-sema`. Two implementations of one decision is the shape
where only one of them gets fixed.

The ClojureScript one exists because `cljs.tools.reader` could not be made to
work under nbb's SCI interpreter — three distinct unresolved-symbol classes in
as many fixes, against a general-purpose reader never designed for SCI. This
library is that reader, promoted out of `kotoba-sema` so both runtimes read
through the same code and the Maven dependency can go.

It covers exactly the admission-gated grammar the frontend accepts: lists,
vectors, maps, sets, keywords, symbols, integers, strings, and `#?()` reader
conditionals. Reader conditionals select `:kotoba` or `:default` — **never a
host feature**, so a `.kotoba` source does not read differently depending on
which runtime is compiling it. That property is what makes one reader possible
at all.

## Integers are not host numbers, and the cost is real

A literal is read as an exact 64-bit integer, not a host number, because
reading `9007199254740993` as a ClojureScript `Number` would lose it *before
compilation started*.

Running this suite on both runtimes for the first time (2026-08-20) measured
what that costs. For the same source `"1"`:

| | JVM | ClojureScript |
|---|---|---|
| `(= … 1)` | **true** | **false** (a `BigInt` object) |
| `(pr-str …)` | `"1N"` | `"#object[BigInt 1]"` |
| `(str …)` | `"1"` | `"1"` |

**`str` is the only rendering the two hosts agree on.** The `pr-str` row is
not a formatting nit: any path that prints a read form — an error message, a
cache key, a digest input — emits `#object[BigInt 1]` on one host and `1N` on
the other, and neither is the source text.

So: do not compare read integers against host literals, and do not `pr-str`
them. Compare `str`, or route through
[`kotoba-lang/i64`](https://github.com/kotoba-lang/i64).

These are pinned as tests rather than described in prose, so they cannot drift
further without going red.

## Surface

```clojure
(r/read-forms source)              ; => sequence of forms
(r/read-forms source opts)         ; opts: :max-depth, :max-token-chars
```

## Verify

```sh
kbb -M:test                                      # JVM
npx nbb@1.4.210 --classpath src:test run-tests.cljk  # ClojureScript
```

Both run the **same** `.cljc` suite: `6 tests, 26 assertions, 0 failures`.
