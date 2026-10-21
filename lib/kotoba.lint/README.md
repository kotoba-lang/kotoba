# kotoba-lang/lint

[![CI](https://github.com/kotoba-lang/lint/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/lint/actions/workflows/ci.yml)

An **EDN source linter/formatter** — the clj-kondo-lite for kotoba/EDN source.
Consumes the sibling libs [`fmt`](https://github.com/kotoba-lang/fmt)
(canonicalize), [`lsp`](https://github.com/kotoba-lang/lsp) (diagnostics),
[`fs`](https://github.com/kotoba-lang/fs) (read source files), and
[`coll`](https://github.com/kotoba-lang/coll) (result shaping). A real consumer
of `fmt` and `lsp` (M5 for both). No third-party deps; every namespace is
`.cljc` (JVM / SCI / ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why

A kotoba cell's source is EDN; before content-addressing it (CID) or running
it, a host wants to (1) check it parses, (2) canonicalize the whitespace so the
CID is stable, and (3) surface any parse error to the editor as an LSP
diagnostic. `lint` composes the stdlib into that one pass — `fmt` canonicalizes,
`lsp` carries the diagnostics, `fs` reads the file, `coll` shapes the result.

## Current surface

`kotoba.lang.lint`:

- `lint-source` — lint an EDN source string → `{:ok? :canonical :diagnostics}`.
  On success, `:canonical` is the `fmt`-canonicalized text and `:diagnostics`
  is empty; on parse failure, `:ok?` is false, `:diagnostics` holds an `lsp`
  diagnostic (`:error` severity, the parse message).
- `lint-file` — read a source file via an injected `IFilesystem` (`fs`), then
  `lint-source`.
- `summary` — count diagnostics by severity (`coll/map-vals`).
- `ok?` — true iff no error-severity diagnostics.

## Install

```clojure
io.github.kotoba-lang/lint {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.lint :as lint])

(lint/lint-source "{:a   1,    :b 2}")
;;=> {:ok? true :canonical "{:a 1, :b 2}" :diagnostics []}
(-> (lint/lint-source "{:a ") :ok?)          ;=> false
(-> (lint/lint-source "{:a ") :diagnostics first :severity) ;=> :error
```

## Verify

```sh
kbb -M:test
```
