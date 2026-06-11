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

- top-level: `(def name <const>)`, `(defn name [params…] body…)`, `(ns …)` (ignored)
- control: `if`, `when`, `cond`, `let` (sequential), `do`, `loop`/`recur` (bounded)
- arithmetic: `+ - * / mod` · comparison: `= < > <= >=` · logic: `and or not`
- strings: `"…"` literals, `(str-len s)`, `(byte-at s i)`
- byte builder: `(bytes-alloc cap)`, `(byte-append! buf b)`, `(bytes-len buf)`,
  `(bytes-finish buf)` — mutable buffer in linear memory; `bytes-finish` → string handle
- raw memory: `(alloc n)`, `(load64 a)`, `(store64! a v)`, `(load32 a)`, `(store32! a v)`
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
- user `defn` calls, including (mutual) recursion

Each `defn` is exported under its name. `def` initialisers are folded to a
compile-time constant and inlined. Every module also exports a linear `memory`
and a `cabi_realloc` bump allocator (the Canonical-ABI substrate).

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
