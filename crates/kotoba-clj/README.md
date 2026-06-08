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
- control: `if`, `when`, `let` (sequential), `do`
- arithmetic: `+ - * / mod` · comparison: `= < > <= >=` · logic: `and or not`
- strings: `"…"` literals, `(str-len s)`, `(byte-at s i)`
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
3. ⬜ `list<u8>` in/out Component export via `wit-component`
4. ⬜ CBOR-decode `InvokeContext` in-guest
5. ⬜ emit `kotoba-node` `run`; load via `WasmExecutor`

Today (steps 1–2) the crate emits a **core wasm module** run on a standalone
`wasmtime` engine — not yet a Component on the `kotoba:kais` world. See
[`docs/ADR-clojure-wasm.md`](../../docs/ADR-clojure-wasm.md).

## Test

```
cargo test -p kotoba-clj   # arithmetic, logic, if/when/let/do, factorial,
                           # fibonacci, mutual recursion, strings (str-len/
                           # byte-at), and the cabi_realloc allocator (align,
                           # monotonic, non-overlap, memory growth)
```
