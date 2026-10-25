# kotoba-lang/strfmt

**printf-style string formatting that produces the same text on every host.**

`(:require [kotoba.strfmt :as f])` — one `.cljc` namespace, one workspace
dependency (`i64`), runs on JVM / ClojureScript / nbb / GraalVM / kotoba-WASM.

## Why this exists

`clojure.core/format` **does not exist on ClojureScript** — it is
`String/format`, JVM-only. Measured 2026-08-20: **57 `(format ...)` call sites
across the compiler stack**, every one of them pinning its file to the JVM,
and nothing owning a portable replacement.

The directive mix is not what a general printf would assume, because this
stack emits opcodes, offsets and digests:

```
%x 39 · %s 15 · %d 4 · %f 3
```

**Hex is the job.** And hex is where the host bites: a 64-bit value rendered
through a JS double loses precision above 2^53, so the digits come from
[`kotoba-lang/i64`](https://github.com/kotoba-lang/i64) rather than from
`Number`.

## Not a full printf, on purpose

It implements the directives that are actually used, with width and
zero-padding, and **refuses anything else rather than passing it through.** A
formatter that silently emits an unrecognised directive verbatim turns a typo
into output — and output is what gets digested.

## Surface

```clojure
(f/format "%x"    255)     ;=> "ff"
(f/format "%04x"  255)     ;=> "00ff"
(f/format "%X"    255)     ;=> "FF"
(f/format "%x"    -1)      ;=> "ffffffffffffffff"   two's complement, not "-1"
(f/format "%04d"  -42)     ;=> "-042"               sign in front of the zeros
(f/format "%-4d"  42)      ;=> "42  "
(f/format "100%%")         ;=> "100%"
(f/format "%q" 1)          ;=> throws
```

Supported: `%s %d %x %X %f %%`, flags `-` and `0`, optional width.

## Not `kotoba-lang/fmt`

`fmt` is a deterministic **EDN source formatter** — the rustfmt equivalent.
This is string formatting. Two different planes that happen to share three
letters.

## Verify

```sh
kbb -M:test                                      # JVM
npx nbb@1.4.210 --classpath src:test:<i64-src> run-tests.cljk
```

Both run the **same** `.cljc` suite: `4 tests, 16 assertions, 0 failures`.

The 64-bit cases take their values from `i64/max-i64` rather than from
literals — a literal that large is read as a double on ClojureScript and is
already wrong before the formatter sees it, so a literal there would test the
reader and fail on the very host this library exists for.
