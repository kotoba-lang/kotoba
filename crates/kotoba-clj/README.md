# kotoba-clj

A **Clojure/EDN-subset → WebAssembly compiler** for kotoba. The Clojure source
literally becomes wasm bytes — this is a compiler, not an embedded interpreter.

```rust
let src = "(defn fact [n] (if (< n 2) 1 (* n (fact (- n 1)))))";
let wasm = kotoba_clj::compile_str(src)?;          // real wasm module
let out  = kotoba_clj::run::run(&wasm, "fact", &[5])?;   // 120
```

```
$ cargo run -p kotoba-clj --example factorial
compiled 105 bytes of wasm (magic: [0, 97, 115, 109])
n= 5  fact=120         fib=5
n=10  fact=3628800     fib=55
```

## `.kotoba` / `.clj` / `.cljc` / `.cljs` files

`kotoba-clj` also installs a runner for Clojure-subset source files. `.kotoba`,
`.clj`, `.cljc`, and `.cljs` are accepted as source extensions:

```clojure
#!/usr/bin/env kotoba-clj
(defn main [x]
  (clojure.core/inc x))
```

```
$ kotoba-clj app.kotoba 41
42
$ kotoba-clj --func fact math.kotoba 5
120
$ kotoba-clj agent.cljc 41
42
```

By default the file runner prepends the kotoba-clj prelude, so common
container helpers such as `count`, `nth`, `get`, and `assoc!` are available.
Use `--no-prelude` for a bare compiler surface.

This is a Clojure compatibility entry point, not JVM Clojure or ClojureScript
runtime compatibility. `.clj` / `.cljc` / `.cljs` files still need to compile to
the kotoba-clj subset below. For `.cljc`, reader conditionals are expanded before
lowering:

```clojure
#?(:kotoba (defn main [x] (+ x 10))
   :clj    (defn main [x] (+ x 1)))
```

The default reader target is `kotoba`, with `:clj` as fallback and `:default`
after that. Use `--reader-target clj` or `--reader-target cljs` to select a
different branch.

`ns` forms may include simple `:require` / `:use` specs; top-level `(require
'[...])` and `(use '[...])` forms are also accepted for script-style files.
Neighboring namespaces are loaded from the entry file's directory using
Clojure-style paths (`demo.util` → `demo/util.clj` / `.cljc` / `.cljs` /
`.kotoba`), and `:as` / `:refer` calls are rewritten before lowering. When
multiple files exist for a namespace, the reader target controls the extension
priority (`kotoba`: `.kotoba`, `.cljc`, `.clj`, `.cljs`; `clj`: `.cljc`,
`.clj`, `.kotoba`, `.cljs`; `cljs`: `.cljc`, `.cljs`, `.clj`, `.kotoba`).
`:as-alias` records a compile-time alias without loading the target namespace.
`clojure.*` and `cljs.*` requires are also not loaded from files; using functions
outside the kotoba-clj subset still fails during lowering/codegen:

```clojure
(ns demo.main
  (:require [demo.util :as u]
            [demo.math :refer [twice]]))

(defn main [x]
  (+ (u/add x 2) (twice x)))
```

This resolver is intentionally small: it does not implement full classpath
semantics, macros, reload semantics, or JVM/CLJS libraries.

Common reader noise is accepted and ignored where it does not affect runtime
semantics: discard forms (`#_`), metadata (`^:private`, `^String`, parameter
metadata), top-level `(comment ...)`, top-level `(declare ...)`, and optional
`def` / `defn` docstrings plus `defn` attr maps. Top-level namespace management
forms (`in-ns`, `alias`, `create-ns`, `remove-ns`), `(refer-clojure ...)`,
`(import ...)`, `(gen-class ...)`, `(set! ...)`, and unused record/type/protocol
or multimethod/struct declarations are accepted as declarations. `defonce` lowers
like `def`, and `defn-` lowers like `defn` for source compatibility. Top-level
`defmacro` forms are accepted for macro-only namespaces loaded via
`require-macros`, but macros are not expanded. Clojure-style multi-arity `defn`
is supported for
source-level calls by resolving on the call's argument count; `defn` pre/post
condition maps are accepted but not asserted. Single-arity definitions remain
exported under their source name. The common threading macros `->`, `->>`,
`cond->`, `cond->>`, `some->`, `some->>`, and `as->` are expanded during
lowering.

The entry file's directory is always searched. If a `deps.edn` is found in the
entry file's directory or one of its ancestors, its top-level `:paths` vector is
also searched. Additional source roots can be provided with repeated
`--source-path` / `-S` flags or the platform path-list environment variable
`KOTOBA_CLJ_PATH`:

```sh
kotoba-clj -S src -S vendor app/main.clj 41
KOTOBA_CLJ_PATH=src:vendor kotoba-clj app/main.clj 41
```

## Pipeline

```
Clojure/EDN source
   │  kotoba_edn::parse_all           (SSoT reader — no second parser)
   ▼
EdnValue tree
   │  ast::parse_program              (lower to typed AST)
   ▼
Program { defs, functions }
   │  codegen::compile                (two-pass; wasm-encoder)
   ▼
WebAssembly core module (bytes)
   │  run::run                        (wasmtime, feature "run", default on)
   ▼
i64 result
```

## Subset

Stack values are 64-bit: a number/boolean is the i64 (booleans `1`/`0`, truthy ⇔
non-zero); a **string** is a packed `(offset << 32) | len` handle into memory.

- top-level: `(def name "doc?" <const>)`,
  `(defonce name "doc?" <const>)`, `(defn name "doc?" attr-map? [params…] body…)`,
  `(defn name "doc?" attr-map? ([params…] body…) ([params…] body…))`,
  `(defn- …)`, top-level `(do …)` wrapping definitions, `(ns …)`,
  `(in-ns …)`, `(alias …)`, `(create-ns …)`, `(remove-ns …)`, `(require …)`,
  `(use …)`, `(refer-clojure …)`, `(import …)`, `(gen-class …)`, `(set! …)`,
  `(defrecord …)`, `(deftype …)`, `(defprotocol …)`, `(extend-type …)`,
  `(extend-protocol …)`, `(defmulti …)`, `(defmethod …)`, `(defmacro …)`,
  `(defstruct …)`, `(create-struct …)`, `(comment …)`, and `(declare …)`
  (ignored where noted)
- control: `if` (2- or 3-form), `if-not`, `when`, `when-not`, `if-let`,
  `when-let`, `cond`, `case`, `let` (sequential), `do`, `comment`, `loop`/`recur`
  (bounded), threading macros `->`, `->>`, `cond->`, `cond->>`, `some->`,
  `some->>`, and `as->`
- binding forms: symbols plus vector and map destructuring in `defn`, `let`,
  `loop`, `if-let`, and `when-let`; vectors support nested destructuring, `_`
  placeholders, `& rest`, and `:as whole`; maps support `{local :key}`,
  `{:keys [...]}`, `{:strs [...]}`, `:or` defaults, and `:as whole`
- arithmetic: `+ - * / quot mod rem inc dec abs min max` · comparison:
  `= not= < > <= >=` (n-ary where Clojure is n-ary) · predicates:
  `nil? some? zero? pos? neg? even? odd?` · logic: `and or not`
- strings: `"…"` literals, `(str-len s)`, `(byte-at s i)`
- Clojure literals: `nil` lowers to `0`; keyword literals and quoted forms
  (`'foo`, `'(a b)`, `(quote {:k 1})`) lower to canonical EDN string handles;
  var quote (`#'foo`, `(var foo)`) lowers to the referenced symbol name handle;
  vector literals (`[1 2]`) and map literals (`{:k v}`) lower to the prelude's
  mutable vector/map handles when the prelude is enabled
- Clojure reader metadata (`^:private`, `^String`, `^long`) is stripped before
  lowering.
- Clojure discard forms (`#_ form`) are stripped before lowering.
- byte builder: `(bytes-alloc cap)`, `(byte-append! buf b)`, `(bytes-len buf)`,
  `(bytes-finish buf)` — mutable buffer in linear memory; `bytes-finish` → string handle
- raw memory: `(alloc n)`, `(load64 a)`, `(store64! a v)`, `(load32 a)`, `(store32! a v)`
- prelude aliases for common Clojure-style container calls: `count`, `empty?`,
  `seq`, `not-empty`, `nth` (2- or 3-arity), `first`, `second`, `last`,
  `peek`, `subvec`, `rest`, `conj!`, `get` (2- or 3-arity), `assoc!`,
  `contains-key?`
- `clojure.core/`-qualified builtin calls are accepted for the supported core
  numeric/comparison/logical operations.
- host calls: `(has-capability? resource ability)` → `auth.has-capability`;
  `(llm-infer model prompt)` → `llm.infer` (ok → output handle, err → `0`);
  `(kqe-assert! g s p obj-cbor)` / `(kqe-retract! …)` → `kqe.assert-quad` /
  `retract-quad` (**Datom write surface**, 1/0); `(kqe-get-objects g s p)` /
  `(kqe-query filter)` → packed list handles, read via `KQE_PRELUDE`
  (`kqe-count`, `kqe-obj-nth`, `kqe-quad-{graph,subject,predicate,object}`)
- in-guest CBOR decode (`CBOR_PRELUDE`): `cbor-reader`, `cbor-uint`, `cbor-text`,
  `cbor-map-seek`, `cbor-skip` — decode a `run(ctx-cbor)` payload in the language
- in-guest CBOR encode (`CBOR_ENC_PRELUDE`): `cbor-enc-uint!`, `cbor-enc-text!`,
  `cbor-enc-map-header!`, `cbor-enc-array-header!` — return a structured result
- `defgraph`: a langgraph-shaped node/edge graph (`:entry`/`:nodes`/`:edges`,
  static + `(if-edge pred? :then :else)` edges) → dispatch/next/runner `defn`s
- user `defn` calls, including (mutual) recursion and arity-based resolution

Each single-arity `defn` is exported under its name. Multi-arity `defn`s are
resolved for source-level calls and Component entry wrapping, but are not
exported as multiple same-name core wasm functions. `def` initialisers are
folded to a compile-time constant and inlined. Every module also exports a
linear `memory` and a `cabi_realloc` bump allocator (the Canonical-ABI
substrate).

## Roadmap to the kotoba:kais binding

Loading compiled Clojure in `kotoba-runtime` requires satisfying the
`kotoba-node` world's `run(ctx-cbor: list<u8>) -> result<list<u8>, string>`
export, which needs memory + an allocator + byte/string values first:

1. ✅ linear memory + `cabi_realloc`
2. ✅ Str/Bytes values (`str-len`, `byte-at`)
3. ✅ `list<u8>` in/out Component export via `wit-component`
4. ✅ CBOR decode/encode in-guest (`CBOR_PRELUDE` / `CBOR_ENC_PRELUDE`)
5. ✅ emit `kotoba-node` `run` — **runs on kotoba-runtime**: `compile_kais_component_str` + the runtime's `WasmExecutor` invokes `run(ctx)` end-to-end (`tests/kais_invoke.rs`)
6. ✅ kqe host builtins — Datom read/write from the guest (`tests/kqe.rs`,
   incl. the Datomic loop: agent asserts → `kotoba_datomic::Db` reads)
7. ✅ Pregel/BSP — the compiled agent runs on `kotoba-vm::WasmPregelRunner`
   across multiple supersteps, asserting Datoms each superstep (`tests/pregel.rs`)

A `(defn run [input] …)` program compiles to a real Component today:

```rust
let comp = kotoba_clj::component::compile_component_str("(defn run [input] input)")?;
let out  = kotoba_clj::component::run_component(&comp, b"hello")?;   // b"hello"
```

Binding to the actual `kotoba:kais` `kotoba-node` world (and meaningfully
reading `ctx`) is steps 4–5. See
[`docs/ADR-clojure-wasm.md`](../../docs/ADR-clojure-wasm.md).

## Test

```
cargo test -p kotoba-clj   # arithmetic, logic, if/when/let/do, factorial,
                           # fibonacci, mutual recursion, strings (str-len/
                           # byte-at), and the cabi_realloc allocator (align,
                           # monotonic, non-overlap, memory growth)
```
