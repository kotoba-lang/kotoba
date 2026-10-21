# kotoba-lang/lint-kotoba

[![CI](https://github.com/kotoba-lang/lint-kotoba/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/lint-kotoba/actions/workflows/ci.yml)

**Static analysis of kotoba/EDN code** — the clj-kondo-lite-deeper for kotoba.
Consumes [`lint`](https://github.com/kotoba-lang/lint) (parse/diagnostics),
[`lsp`](https://github.com/kotoba-lang/lsp) (diagnostic ranges), and
[`coll`](https://github.com/kotoba-lang/coll) (result shaping). Generalizes
`wit`'s `unused_grants` linter into a per-source static-analysis pass. No
third-party deps; `.cljc` (JVM / SCI / CLJS / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why

`lint` formats and parses; `wit`'s `unused_grants` checks capability over-grant
in compiler policy. `lint-kotoba` is the **source-level** static analysis that
sits between: it walks a parsed kotoba/EDN form, collects declared (`def`/`defn`
names) and referenced symbols, reports **unused declarations** and **undeclared
references**, and — when a form declares capability grants — reports
**over-granted** capabilities (granted but not used). All diagnostics are `lsp`
records (range + severity + message), so an editor surfaces them directly.

## Current surface

`kotoba.lang.lint-kotoba`:

- `analyze` — parse `source` (via `lint`) then walk the form tree; returns
  `{:ok? :diagnostics :declared :references :unused :undeclared}`
- `unused-decls` — `def`/`defn` names never referenced elsewhere
- `undeclared-refs` — symbols referenced but not declared (and not in
  `:known-globals`)
- `over-granted-capabilities` — given a form with `:grants` and a set of used
  capability strings, report granted-but-unused (generalizes `unused_grants`)
- diagnostics are `lsp/diagnostic` records

## Install

```clojure
io.github.kotoba-lang/lint-kotoba {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.lint-kotoba :as lk])

(lk/analyze "{:grants [\"store:read\" \"store:write\"]}" :used #{"store:read"})
;; => {:ok? false :unused [] :undeclared [] :diagnostics [<store:write over-grant>]}
```

## Verify

```sh
kbb -M:test
```
