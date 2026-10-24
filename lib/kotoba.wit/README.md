# kotoba-lang/wit

[![CI](https://github.com/kotoba-lang/wit/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/wit/actions/workflows/ci.yml)

**Layer 2 (cap/effect) of the kotoba foundational stdlib** — a WIT (WebAssembly
Interface Types) interface represented as EDN, plus a **deny-by-default
capability-token data model**. This is the *user-facing* face of the existing
`effects.rs` / `policy.rs` enforcement boundary in `kotoba-clj`; it invents no
new gate, it just gives the cell author a typed thing to name and request.
Zero third-party runtime deps; every namespace is `.cljc` (JVM / SCI /
ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md)
and `ADR-safe-capability-language.md`.

## Why

A kotoba cell can only touch what it was explicitly handed. That requires a
vocabulary for *what a host import is* and *what a cell may request*. This lib
makes a WIT interface plain data (`{:wit/interface "kap:kv" :wit/functions …}`)
and a capability a mintable, comparable token
(`{:wit/capability "kap:kv/get" :wit/effects #{:read}}`). A **policy** is a set
of granted tokens; `allows?` is deny-by-default — an ungranted capability is
simply not in the set, the same property the compiler's `policy.rs` enforces.

## Current surface

`kotoba.lang.wit`:

- `interface?`, `function?` — shape predicates
- `capability` — mint a token from `interface-name` + `function-name` (+ `:effects`)
- `capabilities` — all tokens an interface exposes (effects inferred from name
  when not declared: `get`/`read` → `#{:read}`, `put`/`write`/`delete` →
  `#{:write}`, else `#{:call}`)
- `validate-interface` — problem seq (empty = valid)
- `policy` / `grant` / `revoke` / `allows?` — deny-by-default policy algebra

## Install

```clojure
io.github.kotoba-lang/wit {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.wit :as wit])

(def kv-iface
  {:wit/interface "kap:kv"
   :wit/functions [{:name "get" :params [{:name "k" :type "string"}] :result "string"}
                   {:name "put" :params [{:name "k" :type "string"} {:name "v" :type "string"}] :result "bool"}]})

(wit/capabilities kv-iface)
;; => (#:wit{:capability "kap:kv/get" :effects #{:read}}
;;     #:wit{:capability "kap:kv/put" :effects #{:write}})

;; deny-by-default: an empty policy allows nothing
(wit/allows? (wit/policy) "kap:kv/get")            ;=> false
(wit/allows? (wit/grant (wit/policy) "kap:kv/get") "kap:kv/get") ;=> true
```

## Verify

```sh
kbb -M:test
```
