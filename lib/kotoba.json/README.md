# kotoba-lang/json

[![CI](https://github.com/kotoba-lang/json/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/json/actions/workflows/ci.yml)

**Layer 1 (data) of the kotoba foundational stdlib** — pure-Clojure JSON
encode/decode with **no host dependency**. `langchain` and other vertical libs
currently punt JSON parsing to the host; this lib is the in-language
replacement that runs on kotoba-WASM. Zero third-party runtime deps; every
namespace is `.cljc` (JVM / SCI / ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Current surface

`kotoba.lang.json`:

- `encode` — Clojure data → JSON string (deterministic key order: map keys
  sorted, so output is content-addressable)
- `decode` — JSON string → Clojure data (object keys are strings; JSON has no
  keywords)
- `nil` ↔ `null`, `true/false`, integers vs doubles, full string escape set
  (`\" \\ \n \t \r \b \f \/ \uXXXX`), nested arrays/objects

## Install

```clojure
io.github.kotoba-lang/json {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.json :as json])

(json/encode {:name "ada" :age 36})   ;=> "{\"age\":36,\"name\":\"ada\"}"
(json/decode "{\"a\":1,\"b\":[2,3]}")  ;=> {"a" 1 "b" [2 3]}
```

## In-guest field extraction (`.kotoba`)

`kotoba/json_scalar.kotoba` is the first `.kotoba` port in this repo. It is
**not** `decode`. It is one operation — read the string value of a top-level
object member — because that is the operation `amu/runtime/http-service.mjs`
names as blocked:

> No structural JSON parsing *inside* the guest. The body crosses the boundary
> as a validated-syntactically-JSON `:string`; a guest that wants to inspect
> fields must do its own string work (or, once `kotoba-lang/json` has a
> `.kotoba` port, use that).

```clojure
(json-string-field "{\"name\":\"ada\",\"age\":36}" "name")  ;=> some "ada"
(json-string-field "{\"name\":\"ada\"}" "nope")             ;=> none
(json-string-field "{\"age\":36}" "age")                    ;=> none (not a string)
```

It returns `[:option :string]`, never throws (`:explicit-errors` is an
`:intentional-security-constraint`), and requires **zero capabilities**, which
is what `http-service.mjs` demands of a guest module. Members before the
wanted key are skipped *structurally*, so nested objects/arrays and strings
containing `{ } , :` cannot desynchronise the scan, and every step advances by
the code point's UTF-8 width because `string-code-point-at` traps off a
boundary.

Three of JSON's eight escapes are **refused** (return none) rather than
decoded, each for a measured language gap rather than a policy choice:
`\uXXXX` (no code-point → string constructor exists; `string-from-i64` renders
a decimal number, not a character) and `\b` / `\f` (cannot be *written* in
`.kotoba` source — the reader rejects a file containing those literals). See
the module header and ADR-2608292330.

Input size is bounded by fuel, which is charged per function entry and baked
in at compile time. Budget roughly one unit per input byte:

```sh
amu compile "$PWD/kotoba/json_scalar.kotoba" --target js \
  --fuel 200000 --output /tmp/json_scalar.mjs
```

## Verify

```sh
kbb -M:test                      # the .cljc suite
kbb --backend sci scripts/kotoba_test.cljk         # the .kotoba suite, on :jvm-kir :js :wasm
```

`scripts/kotoba_test.cljk` splices each batch in `test/kotoba/*.kotoba-part`
onto the library source and runs amu's official `amu test` harness, so every
case runs on all three semantic targets. It needs `amu` on `PATH`, at
`../amu/bin/amu` (the west layout), or at `$AMU`. It exits 2 — not 1 — when
the suite could not be *run*, so "could not answer" never looks like "passed".
