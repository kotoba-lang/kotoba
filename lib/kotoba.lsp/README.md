# kotoba-lang/lsp

[![CI](https://github.com/kotoba-lang/lsp/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/lsp/actions/workflows/ci.yml)

**Layer 4 (tooling) of the kotoba foundational stdlib** — an LSP-style document
model: positions, ranges, diagnostics, and a simple text document as **pure
data**. No JSON-RPC transport is baked in (a capability-confined kotoba cell
gets the wire from the host) — this lib owns the *data contract* an editor or
`kotoba` CLI tool speaks. No third-party deps; every namespace is `.cljc`
(JVM / SCI / ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Current surface

`kotoba.lang.lsp`:

- `position`, `range`, `diagnostic` — data constructors
- `text-document` — a line-indexed document from source text
- `position->offset`, `offset->position` — convert between LSP positions and
  character offsets
- `diagnostic` severities (`:error :warning :information :hint`)
- `within-range?`, `contains-position?` — range queries

Positions are 0-based `{line character}` (matching LSP). A `diagnostic` is
`{:range :severity :source :message}`.

## Install

```clojure
io.github.kotoba-lang/lsp {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.lsp :as lsp])

(def doc (lsp/text-document "line0\nline1\nline2"))
(lsp/position->offset doc {:line 1 :character 2})   ;=> 7
(lsp/offset->position doc 7)                          ;=> {:line 1 :character 2}
(lsp/diagnostic (lsp/range (lsp/position 0 0) (lsp/position 0 4))
                :error "parse" "bad form")
```

## Verify

```sh
kbb -M:test
```
