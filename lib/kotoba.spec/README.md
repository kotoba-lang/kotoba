# kotoba-lang/spec

[![CI](https://github.com/kotoba-lang/spec/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/spec/actions/workflows/ci.yml)

**Layer 1 (data) of the kotoba foundational stdlib** — a small data-spec
`validate` / `explain` with **no `clojure.spec` or `malli` dependency**, so it
runs on kotoba-WASM (SCI). Zero third-party runtime deps; every namespace is
`.cljc` (JVM / SCI / ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

A spec is plain EDN data:

```clojure
{:type :map
 :closed? true
 :keys {:name {:type :string}
        :age  {:type :int :optional? true}}}
```

## Why not clojure.spec?

`clojure.spec` is JVM-rooted and not portable to the kotoba-WASM host. kotoba
needs a spec that is plain data + pure functions, so the same contract runs in
an untrusted capability-confined cell. This lib is that contract. It is the
zod / pydantic / serde / malli equivalent for kotoba, and its `explain` output
is designed to feed `kotoba-lang/test` property cases (M5).

## Current surface

`kotoba.lang.spec`:

- `validate` — returns the value if valid, `::invalid` otherwise
- `valid?` — boolean
- `explain` — a list of problem maps `{:path [...] :in [...] :val ... :reason ...}`
- primitive types: `:any :string :keyword :boolean :int :double`
- composite types: `:map` (with `:keys` / `:optional?` / `:closed?`),
  `:vector` (with `:of`), `:set` (with `:of`)
- `:fn` — a predicate spec (`{:type :fn :pred some?}`)

## Install

```clojure
io.github.kotoba-lang/spec {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.spec :as spec])

(def person-spec
  {:type :map
   :closed? true
   :keys {:name {:type :string}
          :age  {:type :int :optional? true}}})

(spec/valid? person-spec {:name "ada"})            ;=> true
(spec/valid? person-spec {:name "ada" :extra 1})   ;=> false (closed)
(spec/explain person-spec {:age "x"})              ;=> problems for :name (missing) and :age (type)
```

## Verify

```sh
kbb -M:test
```
