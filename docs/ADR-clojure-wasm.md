# ADR — Clojure-on-WASM for kotoba (`kotoba-clj`)

Status: **Accepted (steps 1–2 of the kais-binding workstream implemented)**
Date: 2026-06-08
Crate: `crates/kotoba-clj`

## Context

kotoba already runs WASM in two senses:

- `kotoba-runtime` is a **Component-Model host** (wasmtime + WIT world
  `kotoba:kais`) that runs guests written in Rust / Python / JS / Go / C.
- `kotoba-edn` is the SSoT reader for EDN — the Clojure/Datomic wire format.

What did *not* exist was a path where a **Clojure-language program is itself
compiled to WebAssembly**. "Clojure" appeared in the tree only as (a) the EDN
data notation and (b) Datalog builtin name aliases (`clojure.string/*`,
`clojure.set/*`) in `kotoba-datomic`. Neither is a language runtime.

This ADR introduces `kotoba-clj`: a compiler that reads a Clojure/EDN subset and
emits real WebAssembly bytes. The Clojure source *becomes* the wasm module — it
is a compiler, not an embedded interpreter.

## Decision

### Front-end: reuse `kotoba-edn`

Clojure source is read as EDN s-expressions via `kotoba_edn::parse_all`. No
second reader. The `EdnValue` tree is lowered to a typed AST (`ast.rs`).

### Value model (phase 1): i64

Every value is a 64-bit signed integer; booleans are `1`/`0`; a value is truthy
iff non-zero. This keeps the wasm type story trivial (one `ValType::I64`) so the
first slice can focus on getting **call / local / branch** codegen correct.

### Supported subset

| category    | forms |
|-------------|-------|
| top-level   | `(def name <const>)`, `(defn name [params…] body…)`, `(ns …)` ignored |
| control     | `if`, `when`, `let` (sequential), `do` |
| arithmetic  | `+ - * / mod` |
| comparison  | `= < > <= >=` |
| logic       | `and or not` (short-circuit; return 0/1) |
| strings     | `"…"` literals, `(str-len s)`, `(byte-at s i)` |
| application | user `defn` calls, incl. (mutual) recursion |

`def` initialisers are evaluated at compile time and inlined. Each `defn` is
exported under its own name.

### Strings & the memory substrate (steps 1–2)

A string is a packed `(offset << 32) | len` i64 handle into linear memory, so
the "one i64 per expression" stack discipline is preserved. String literals are
laid out in an active data segment at offset `1024`; the bump heap starts
immediately above. Every module also exports:

- `memory` — a single linear memory (grows on demand).
- `cabi_realloc(old, old_sz, align, new_sz) -> ptr` — the Canonical-ABI bump
  allocator the Component Model host calls to lower values into guest memory.
  No free; aligns up and bumps a heap global, growing memory by whole pages when
  a request would overflow the current size.

This is the linear-memory foundation that steps 3–5 build on.

### Codegen: two-pass, via `wasm-encoder`

A deliberate two-pass emit so recursion and mutual recursion work:

1. **Pass 1** assigns every `defn` a stable type-index + function-index and
   evaluates every `def` to a compile-time constant. The function-index table
   exists *before* any body is emitted.
2. **Pass 2** emits bodies, which may freely `call` any function (including
   themselves and not-yet-emitted peers) by an index that already exists.

Params are wasm locals `0..arity`; `let` bindings extend from there. Comparisons
produce i32 and are extended back to i64; `if`/`and`/`or` lower to wasm
`if`/`else` blocks with an `i64` result type.

### Runner (phase 1): standalone wasmtime

`run.rs` (feature `run`, default on) instantiates the emitted **core module** on
a plain `wasmtime::Engine` and calls an exported function with i64 args. This
inherits the workspace-pinned wasmtime (`"22"`) and is native-only, consistent
with the repo rule that wasmtime is not compiled to wasm32.

## Phase boundary (explicit, non-overclaim)

**This is the most important part of the ADR.** Phase 1 emits a **core wasm
module** and runs it on a standalone wasmtime instance. It does **not** yet emit
a WASM **Component** bound to the `kotoba:kais` WIT world, and it does **not**
plug into `kotoba-runtime`'s `WasmExecutor`. So:

- ✅ "A Clojure program compiles to real wasm and runs." — **true today.**
- ❌ "Clojure programs run as first-class kotoba node programs on
  `kotoba-runtime` alongside the Rust/Python/JS/Go/C guests." — **not yet.**

## Roadmap (corrected dependency order)

The phase-1 ADR listed "Component Model" before "richer values". That order is
**inverted**: the `kotoba-node` world's export is
`run(ctx-cbor: list<u8>) -> result<list<u8>, string>`. Satisfying it requires
the guest to CBOR-decode/encode `list<u8>` — which needs linear memory, a
`cabi_realloc` allocator, and byte/string values *in the language itself*. An
i64-only language has nothing meaningful to put in a `list<u8>`. So
bytes/memory is the **prerequisite** for the kais binding, not a follow-on. The
real step order:

1. ✅ **Linear memory + `cabi_realloc`** (bump allocator, grows memory).
   Exported by every module. Core-level tested (alignment / monotonicity /
   non-overlap / growth).
2. ✅ **Str/Bytes values** — strings as packed `(offset << 32) | len` handles
   into a data segment; builtins `str-len`, `byte-at`.
3. ⬜ **`list<u8>` in/out Component export** via `wit-component`: generate a
   WIT world, embed component metadata, encode the core module to a Component,
   instantiate + invoke through `wasmtime::component`. This is exactly the
   Canonical-ABI list machinery the kais `run` export reuses.
4. ⬜ **CBOR-decode `InvokeContext`** `{ graph, session_cid, args_cbor }`
   in-guest; CBOR-encode the output.
5. ⬜ **Emit the `kotoba-node` `run` export**; verify `ProgramStore` /
   `WasmExecutor` can load and invoke it. `program_cid = CIDv1 blake3(wasm)`,
   stored in Vault/Shelf like every other program. Then bind host imports
   (`kqe` assert/query, `kse` publish/drain, `auth`, `llm`) and honour the gas
   model (assert=10, query=100, llm.infer=1000).

## Consequences

- kotoba gains a native Lisp surface: programs can be authored in EDN (the
  format the database already speaks) and compiled to the substrate the runtime
  already runs.
- Phase 1 is self-contained and verifiable (`cargo test -p kotoba-clj`:
  arithmetic, comparison/logic, `if`/`when`/`let`/`do`, factorial, fibonacci,
  mutual recursion, def-inlining, error reporting). The discriminating tests are
  the recursive ones — a flat `(+ a b)` proves almost nothing about codegen.
- The Component-Model gap is documented rather than hidden, so the next
  increment has a clear, bounded scope.
