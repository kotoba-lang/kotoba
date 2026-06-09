# ADR — Clojure-on-WASM for kotoba (`kotoba-clj`)

Status: **Accepted (steps 1–3 + 5 done; runs on kotoba-runtime. Only step 4 left)**
Date: 2026-06-08 (steps 1–2), 2026-06-09 (steps 3 + 5, incl. live invoke)
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
3. ✅ **`list<u8>` in/out Component export** via `wit-component` (module
   `component`): a `(defn run [input] …)` becomes a Component exporting
   `run: func(list<u8>) -> list<u8>` on a self-owned `kotoba:clj-program` world,
   instantiated + invoked through `wasmtime::component`. A hand-emitted
   Canonical-ABI wrapper packs the input `(ptr,len)` into a string handle, calls
   the user function, and writes the returned handle's `(ptr,len)` into a
   `cabi_realloc`'d return area. This is exactly the list lift/lower machinery
   the kais `run` export reuses. **De-risked first** with a scalar smoke test
   (`examples/component_smoke.rs`) confirming `wit-component` 0.221 output
   instantiates in the pinned wasmtime 22.
4. ⬜ **CBOR-decode `InvokeContext`** `{ graph, session_cid, args_cbor }`
   in-guest; CBOR-encode the output. **Blocked**: a CBOR decoder needs iteration
   and byte-building, which the i64+strings language does not yet have. This is
   a separate, larger language workstream (loops + a `bytes` builder), not a
   codegen detail — see "Language-growth dependency" below.
5. ✅ **Emit the `kotoba-node` `run` export — and run it on kotoba-runtime.**
   `compile_kais_component_str` targets the real `kotoba-node` world from
   `kotoba-runtime/wit` (resolved via `Resolve::push_dir`, deps incl. wasi:http)
   and emits `run: func(ctx-cbor: list<u8>) -> result<list<u8>, string>` (the
   `ok` case: 12-byte return area `[tag:u8=0, ptr, len]`). `assert_loads`
   confirms `Component::new` accepts it (the `ProgramStore::get_or_compile`
   path). **`tests/kais_invoke.rs` then drives the runtime's own `WasmExecutor`**
   (a dev-dependency) which binds every `kotoba:kais` interface, instantiates the
   component, calls `run(ctx)` and lifts the `result<list<u8>, string>` — proving
   compiled Clojure runs end-to-end on kotoba-runtime, and validating the
   hand-emitted variant layout at runtime (a mis-layout would trap the lift).
   **Remaining for full production parity** (not blocking the milestone):
   `program_cid = CIDv1 blake3(wasm)` storage in Vault/Shelf and honouring the
   gas model (assert=10, query=100, llm.infer=1000) when the guest calls host
   fns — our guest calls none, so it consumes no gas. And the wrapper passes raw
   `ctx-cbor` to the program **undecoded**: meaningfully reading ctx/args is
   gated on step 4.

## Two capability boundaries (what "runs on kotoba-runtime" does and does not mean)

The live invoke proves the *plumbing*, not a functional node program. Be precise:

> Compiled Clojure **computes over bytes and returns bytes, on the real
> runtime.** It cannot yet (a) **read** its `ctx`/`args` — the wrapper hands the
> program the raw `ctx-cbor` undecoded; nor (b) **call** any kotoba host service
> — the emitted guest has *no import section*, so `kqe`/`kse`/`auth`/`llm` are
> bound by the linker but unreachable from Clojure (no builtin lowers to a WIT
> import).

Both gaps are language-growth, not codegen: (a) needs a CBOR decoder (loops +
byte-building); (b) needs builtins that lower to the `kotoba:kais` imports
(e.g. `(kqe/assert …)` emitting an imported-function call). Until then the test
suite's green is plumbing-green, not reachable-surface-green.

## Language-growth dependency (steps 4+)

Everything through step 3 works because the program's I/O is "bytes in → a
handle to bytes already in memory out" — no value needs to be *constructed* at
runtime. The moment a program must **decode** CBOR (step 4) or **build** a CBOR
reply, it needs:

- **iteration** — `loop`/`recur` or a bounded `while`, to walk input bytes;
- **byte-building** — a way to allocate (via `cabi_realloc`) and write bytes,
  i.e. a mutable `bytes`/`string-builder` value, not just read-only handles.

These are language features, not wrapper glue. Hand-emitting a CBOR parser as
raw wasm would be the canonical-ABI-by-hand trap in a different costume, so it
is explicitly **out of scope** until the language grows these primitives.

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
