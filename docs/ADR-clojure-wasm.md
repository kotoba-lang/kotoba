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

## Closing (2026-06-09)

Steps **1, 2, 3, 5** are implemented and verified; **step 4** is the single
remaining item and is deliberately deferred. As of this ADR:

- A Clojure-subset program compiles to a real WASM **Component** and, via the
  runtime's own `WasmExecutor`, **runs end-to-end on kotoba-runtime** —
  computing over bytes and returning bytes through the actual `kotoba-node`
  `run: func(list<u8>) -> result<list<u8>, string>` export.
- 27 tests + doctest green; `cargo check --workspace` clean. The live invoke
  (`tests/kais_invoke.rs`) is the dispositive proof — it exercises the
  hand-emitted Canonical-ABI variant layout at runtime, which a compile-only
  load check could not.

**What "runs on kotoba-runtime" does *not* yet mean** — two boundaries remain,
both **language-growth, not codegen**:

1. **Reads nothing.** The wrapper hands the program the raw `ctx-cbor`
   undecoded; a program that meaningfully reads `ctx`/`args` needs a CBOR
   decoder = iteration + byte-building (step 4).
2. **Calls nothing.** The emitted guest has *no import section*, so
   `kqe`/`kse`/`auth`/`llm` are bound by the host linker but unreachable from
   Clojure; calling a host service needs builtins that lower to the
   `kotoba:kais` imports (e.g. `(kqe/assert …)`).

**Next workstream (not started — needs an explicit go-ahead):** grow the
language — (1) iteration, (2) a mutable byte/string-builder backed by
`cabi_realloc`, (3) a CBOR decoder, (4) host-call builtins. (1)+(2) are the
foundation everything else depends on. Production parity also wants
`program_cid = CIDv1 blake3(wasm)` storage and gas accounting once guests call
host fns (today's guests call none → zero gas).

---

## Step 4a — language growth: iteration + byte-building (DONE, 2026-06-09)

Status: **Accepted.** Crate: `crates/kotoba-clj` (`tests/loops_bytes.rs`, 13 tests).

The "Next workstream" items (1) iteration and (2) a mutable byte-builder — the
foundation step-4 CBOR decode depends on — are implemented. The value model is
unchanged (still one `i64` per expression); no GC, no heap objects beyond the
raw byte region. Added surface:

| form | lowering |
|------|----------|
| `(loop [b v …] body…)` | wasm `loop (result i64)`; sequential-init bindings become a `recur` target |
| `(recur args…)` | parallel rebind of the loop locals + `br` to the loop header (relative label = `ctrl_depth − loop_frame_depth`); must be in tail position |
| `(cond t1 e1 … :else ed)` | right-nested `if`; `:else`/`true` = default; no match ⇒ `0` |
| `(bytes-alloc cap)` | `cabi_realloc(0,0,16,cap+8)` → buffer handle (i64 ptr to an 8-byte header `[cap:i32@0, len:i32@4]` + data) |
| `(byte-append! buf b)` | `mem[buf+8+len] = b & 0xFF; len++`; returns `buf` (threads through `recur`) |
| `(bytes-len buf)` | `mem[buf+4]` |
| `(bytes-finish buf)` | string handle `((buf+8) << 32) \| len` — readable by `str-len`/`byte-at` |

Codegen mechanics: `FnCtx` gained `ctrl_depth` (count of open wasm control
frames) and a `loop_targets` stack so `recur` computes its relative `br` index
correctly through nested `if`/`cond`/`let`. `recur` is stack-polymorphic via
`br`, so it type-checks in any `i64` result slot. A **buffer handle** (ptr to
header) is deliberately distinct from a **string handle** (`ptr<<32|len`):
builder ops take the former, readers the latter, `bytes-finish` converts. No
capacity check yet (caller sizes via `bytes-alloc`); auto-grow is a later
refinement.

Verified end-to-end on wasmtime: Σ/gcd loops, `recur` nested inside
`cond`/`let`/`if`, buffer build-in-loop → finish → re-read sum, and a direct
linear-memory inspection confirming `bytes-finish` yields a real readable
region (`🐍` U+1F40D bytes round-trip).

## Direction: kotoba-clj → langgraph (Graph-as-data, staged)

Decision (2026-06-09): target a **Graph-as-data** surface mirroring the existing
kotoba `StateGraph` (ADR-2605250002), **running on kotoba-runtime**. Graph
topology is declared as EDN; only node *bodies* are clj `defn`s; the state dict,
reducers, edge routing, run-loop, and CBOR glue are emitted by the compiler / a
fixed driver. This keeps language growth minimal vs. a full Clojure (no
closures/GC needed to ship a working agent).

```clojure
(defgraph chatbot
  :state {:messages add-messages}     ; reducer per channel
  :nodes {:chat my-chat-fn}
  :edges [[:start :chat] [:chat :end]])

(defn my-chat-fn [state]              ; node body: pure-ish clj
  (assoc state :messages (llm-infer model-cid (last-message state))))
```

Stages (A–D all done; each reuses the prior). A `defgraph` agent now decodes a
CBOR ctx, runs a node/edge graph, calls the LLM, and returns output — entirely
in compiled Clojure on kotoba-runtime:

- **A ✅ language core** — `loop`/`recur`, `cond`, byte-builder (this section).
- **B ✅ heap values** — growable `vector` + string-keyed `map`, enough for a
  `state` map holding a `messages` vector and the `add_messages` (extend)
  reducer. Implemented *in the language itself* (`PRELUDE`) on three new raw
  builtins — `alloc` / `load64` / `store64!` (+ `load32`/`store32!`) — rather
  than hand-emitted wasm: containers are readable clj, and the i64-only model is
  preserved (handles are raw pointers; no GC, bump-only). `tests/heap_values.rs`
  (8 tests) covers vector conj/count/nth, map assoc/get/overwrite with content-
  compared string keys, the extend reducer, and a state-map-holds-messages-
  vector round-trip.
- **C  CBOR + host imports** — now feasible (loops+bytes+maps): decode the
  `InvokeContext` `ctx-cbor` and encode `result<list<u8>,string>`; surface
  `llm.infer` / `kqe.*` / `kse.*` as builtins lowering to the `kotoba-node` WIT
  *imported* functions (the guest grows a real import section + gas).
  - **C-1 ✅ host-import plumbing** — the guest now grows a real wasm **import
    section** and calls a `kotoba:kais` host function. First builtin:
    `(has-capability? resource ability)` → `auth.has-capability:
    func(string,string)->bool`. Picked deliberately as the simplest Canonical
    ABI shape: 4 flat i32 params, single i32 result, **no indirect return
    area**. `compile_core` gained host-import collection + the function-index
    shift (imports occupy `0..N`; every defined fn / `cabi_realloc` / `run`
    wrapper offsets by `N`) — the one correctness-critical change. Each `string`
    arg is unpacked to its `(ptr,len)` flat pair. Verified **end to end on the
    real host**: `tests/host_import.rs` (3 tests) live-invokes through
    `WasmExecutor` (which binds `auth.has-capability`) with the answer driven by
    the `quad_snapshot` — `ComponentEncoder::…validate(true)` confirms the
    hand-emitted import signature, and the live call confirms the wiring.
  - **C-2 ✅ `llm.infer` (return-area imports)** — `infer: func(string,
    list<u8>) -> result<list<u8>,string>` flattens to >1 result, so it lowers
    with an indirect **return-area pointer**: the guest `cabi_realloc`s a 12-byte
    area, appends its pointer as the trailing call param, and reads back the
    variant `[tag@0, ptr@4, len@8]` — `ok` → output string handle, `err` → the
    `0` nil sentinel (no exceptions in the i64 model). `(llm-infer model prompt)`
    is the langgraph node primitive. Verified live: `tests/llm_infer.rs` (3
    tests) drives `WasmExecutor::with_inference` (ok: lifts model text, incl. a
    prompt-echo proving the guest lowered the prompt bytes) and the default
    executor (err → "ERR"). **A compiled-Clojure guest now calls an LLM on
    kotoba-runtime and gets text back.**
  - **C-3 ✅ CBOR decode (in-guest)** — `CBOR_PRELUDE`: a CBOR reader written in
    the language (Stage-A `loop`/`recur`+`byte-at`, Stage-B `str-eq?`), **no
    bitwise ops** — a head byte splits as major `(/ b 32)` / info `(mod b 32)`,
    multi-byte lengths assemble with `(* 256)`. Supports major 0/1/2/3/4/5 and
    inline/1/2/4-byte lengths (8-byte / indefinite / tags / floats deferred). A
    *reader* is a heap cell `[ctx-handle, pos]`; `cbor-text` slices a string
    handle into the ctx; `cbor-map-seek` positions at a text key's value
    (skipping others via recursive `cbor-skip`). **This closes the original
    step-4 blocker.** `tests/cbor.rs` (10 tests): pure decode of uint
    (inline/1/2/4-byte) / text / map-seek+skip built in-guest, **plus** a live
    `decode_ctx_extract_prompt_call_llm` — `ciborium` (the runtime's own CBOR
    lib) encodes `{"prompt":"ping"}`, the guest decodes it through
    `WasmExecutor`, extracts the prompt, and calls `llm.infer` → `"echo:ping"`.
    **A complete single-node agent: decode ctx → call model → return output.**
    Remaining for full fidelity: decoding the 3-field `InvokeContext` wrapper
    itself (same machinery; today tests pass the args map as the ctx).
  - **C-4 ✅ CBOR encoder (in-guest)** — `CBOR_ENC_PRELUDE`, the symmetric
    counterpart so an agent returns a *structured* `result` (map / array / text /
    uint) instead of a raw byte string. Built on the Stage-A byte builder; a head
    is `(major*32 + info)` and multi-byte lengths emit big-endian via `/`/`mod`.
    `cbor-enc-uint!` / `-text!` / `-bytes!` / `-map-header!` / `-array-header!`.
    `tests/cbor_encode.rs` (6 tests): in-guest encode→decode round-trips (uint /
    text / map-seek / 2-byte length) **plus interop** — `ciborium` decodes a
    guest-built `{"reply":"ok","n":7}` map and `[1,2,3]` array to exactly those
    structures, proving the output is spec-conformant CBOR a host can read.
- **D ✅ `defgraph` DSL** — `(defgraph name :entry :n0 :nodes {:n0 fn0 …} :edges
  {:n0 :n1, :n2 (if-edge pred? :a :b)})` lowers (pure AST desugar, no new runtime)
  to three generated `defn`s: `name-dispatch [nid state]` (cond → call node fn),
  `name-next [nid state]` (cond → successor id; static edge or `(if-edge pred?
  :then :else)` → `(if (pred? state) …)`), and `name [state]` (a `loop`/`recur`
  that dispatches, advances from the new state, and runs to the `-1` END
  terminator). Node keywords are compile-time-only (assigned int ids), so nothing
  keyword-shaped exists at runtime; state is the Stage-B `map`. `tests/defgraph.rs`
  (4 tests): static linear graph, an `if-edge` loop (tick-until-done), an
  `if-edge` branch, **and the capstone** `live::cbor_ctx_through_defgraph_to_llm`
  — a langgraph-shaped agent on `WasmExecutor` that decodes a `ciborium` CBOR ctx
  (C-3), builds the state map (B), runs the graph (D), calls `llm.infer` (C-2),
  and returns the reply. **The full A→D stack composes end-to-end.**
  - **D-reducers ✅ automatic per-channel merge** — declaring `:state {:messages
    add-messages :count :override}` switches on langgraph reducer semantics: a
    node returns a *partial-update* map and the generated `name-merge [state
    update]` folds it in — `add-messages` channels **extend** the running vector
    (adopt on first write), others are last-write-wins `map-assoc!`. Opt-in:
    without `:state`, nodes still return the full next state (no merge), so the
    simpler graphs above are unchanged. `tests/defgraph.rs` +2:
    `add_messages_reducer_extends_across_nodes` ([10]→[10,20,30]) and
    `override_reducer_is_last_write_wins`.
  Deferred refinement: `graph_def_cid` derivation from sorted topology (matching
  the StateGraph rule) for content-addressed graph caching.
- **C-5 ✅ kqe host builtins — the Datomic surface (2026-06-11)** — the guest
  can now **read and write Datoms**: `(kqe-assert! g s p obj-cbor)` /
  `(kqe-retract! …)` lower to `kqe.assert-quad` / `retract-quad` (the WIT
  `quad` record flattens to 8 i32 params; the `result<_, string>` return is
  indirect via a 12-byte area → builtin yields 1/0), `(kqe-get-objects g s p)`
  lowers to `get-objects` (host **lifts** `list<list<u8>>` into guest memory
  through our `cabi_realloc`; builtin yields a packed `(ptr<<32)|count` list
  handle), and `(kqe-query filter)` lowers to `query` (`result<list<quad>,
  string>`, 32-byte quad records). The new `KQE_PRELUDE` reads the lifted
  arrays *in the language* (`kqe-count`, `kqe-obj-nth`,
  `kqe-quad-{graph,subject,predicate,object}` via `load32` → string handles).
  `tests/kqe.rs` (9 live tests on `WasmExecutor`): assert/retract land in
  `InvokeResult::{assert,retract}_quads` with guest-built CBOR objects (10 gas
  each), a 5-datom `loop`/`recur` write burst, list lifts (count + element
  bytes + all four quad fields verified in-guest via `str-eq?`), a
  read-modify-write agent (read `kg/role` → assert derived `kg/verified`),
  **and the Datomic loop**: agent-asserted quads → `kotoba_query::Datom` →
  `kotoba_datomic::Datom::from_kqe` → `Db::from_datoms` → `datoms()` returns
  the agent's facts as EDN (`kg/name = "Alice"`, `kg/role = "admin"`) —
  **compiled Clojure writes, the Datomic facade reads.**
- **E ✅ Pregel/BSP verification (2026-06-11)** — `tests/pregel.rs` (3 tests)
  drives the compiled component through **`kotoba-vm::WasmPregelRunner`** (the
  Pregel BSP engine, single-vertex self-loop): each superstep the guest
  CBOR-decodes its ctx (C-3), runs a `defgraph` (D) whose node `kqe-assert!`s a
  tick Datom (C-5) and bumps the counter, then emits `{"status":
  "continue"|"done", "n": k}` (C-4); the runner feeds `continue` output back as
  the next superstep's ctx. Verified: a 4-superstep run (n 0→4) accumulates
  exactly 4 Datoms + ≥40 gas across supersteps with a structured `done` output;
  a 1-superstep immediate halt; and the `max_supersteps` cap stopping a
  continue-loop at the BSP boundary. **A langgraph-shaped compiled-Clojure
  agent runs on Pregel BSP, writing Datoms every superstep.**

---

## R1 — `.kotoba` source files and Clojure-core compatibility (DONE, 2026-06-11)

Status: **Accepted.** Crate: `crates/kotoba-clj`.

`kotoba-clj` now has a file runner for Clojure-subset source files using the
`.kotoba` extension, matching the operational shape of `clj` / `bb` scripts:

```clojure
#!/usr/bin/env kotoba-clj
(defn main [x]
  (clojure.core/inc x))
```

```text
kotoba-clj app.kotoba 41
kotoba-clj --func fact math.kotoba 5
kotoba-clj --wasm-out app.wasm app.kotoba
```

The runner strips a leading Unix shebang before the EDN reader sees the source,
prepends the kotoba-clj prelude by default, validates the `.kotoba` extension
unless `--allow-any-ext` is passed, and invokes exported `main` unless
`--func` selects another exported function. `compile_file` and
`compile_file_with_prelude` expose the same behavior to Rust callers.

The supported Clojure-core compatibility surface also grew:

- `clojure.core/`-qualified supported builtins resolve to their unqualified
  names.
- Numeric aliases and predicates: `quot`, `rem`, `inc`, `dec`, `abs`, `zero?`,
  `pos?`, `neg?`.
- Clojure-style n-ary comparisons: `=`, `not=`, `<`, `>`, `<=`, `>=`.
- Prelude container aliases over the existing vector/map heap representation:
  `count`, `empty?`, `nth`, `first`, `last`, `conj!`, `get`, `assoc!`,
  `contains-key?`.

Verification: `cargo test -p kotoba-clj` passed, including `.kotoba` file
execution and shebang tests. Datomic query compatibility gained a regression
test for `clojure.core/`-qualified collection functions in
`kotoba-datomic::q`.

## Anonymous functions & closures (`(fn …)` / `#(…)`) — 2026-06-13

First-class anonymous functions now compile via **lambda lifting** to a WASM
funcref table + `call_indirect`. This is milestone 1 toward running
`langgraph-clj` / `langchain-clj` (the portable `.cljc` LangGraph/LangChain
implementations) on kotoba-clj/WASM, since both lean heavily on `(fn …)`.

### Reader (`kotoba-edn`)

`#(…)` is desugared in the EDN reader: `parse_dispatch` routes `#(` to
`parse_anon_fn`, which reads the body list, scans the implicit args
(`%`/`%1`..`%9` → arity = max index; `%&` → rest), normalises bare `%` to `%1`,
and rewrites to `(fn [%1 … %N] body)`. Nested `#(…)`/`(fn …)` are **not**
descended into (their `%` args belong to them). `#(+ % 1)` → `(fn [%1] (+ %1 1))`.

### AST + lambda lifting (`kotoba-clj::ast`)

`Expr` gains four nodes: transient `Fn { params, body }`; and the post-lift
`MakeClosure { table_slot, captures }`, `ClosureRef(slot)`, and
`CallValue { f, args }`. `lift_program` runs after parsing and:

1. rewrites every `(fn …)` site to a `MakeClosure` plus a synthetic top-level
   `Function` whose first parameter `__self` is the closure record pointer;
2. computes free **lexical** variables (enclosing locals the body references,
   minus inner binders) — these become the captures, in first-occurrence order;
3. inside the lifted fn, each captured reference becomes `ClosureRef(slot)`
   (a load from `__self`); params/lets stay real locals;
4. rewrites any call whose head names a lexical binding (a local/captured
   closure, or a higher-order parameter like `(defn ap [f x] (f x))`) into a
   `CallValue` — direct `Call` is reserved for top-level `defn`s.

Nested closures capture transitively: an inner fn that references a variable
which is itself a capture of the outer fn captures the outer's `ClosureRef`
value at closure-construction time (verified by test).

### Codegen (`kotoba-clj::codegen`)

- Closure record on the bump heap: `[table-slot:i64 @0, cap0:i64 @8, …]`; the
  value is the record pointer as an i64 handle.
- `MakeClosure` → `cabi_realloc` the record, store the slot + captures, yield the
  pointer. `ClosureRef(n)` → load `mem64(8 + 8n)` off `local 0` (`__self`).
- `CallValue` → push `__self` + args, load the slot from record[0], and
  `call_indirect` the single funcref table (type = `(N+1)×i64 → i64`).
- A new `table` (section 4) + active `element` segment (section 9) list the
  lifted functions; `arity_type` lets `call_indirect` pick the right type index.

### Honest scope

Fixed-arity only: variadic `& rest` / `%&` and multi-arity `(fn ([a] …) …)` are
rejected with a clear error. `(fn …)` is not yet self-recursive (a self-name is
parsed but unbound). Full `langgraph-clj` additionally needs HOFs over seqs
(`map`/`filter`/`reduce`) and protocols — later milestones.

Verification: `cargo test -p kotoba-edn` (27, incl. 5 `#(…)` reader tests) and
`cargo test -p kotoba-clj --features run,component` (incl. the 9-test
`tests/closures.rs` end-to-end suite: head-position application, reader macro,
let/param capture, bound-then-called, higher-order param, distinct table slots,
**escaping returned closure**, **nested transitive capture**) all green; clippy
clean.

## Higher-order sequence functions (`map`/`filter`/`reduce`/…) — 2026-06-14

With closures + `call_indirect` in place (previous section), the seq HOFs are
written as **ordinary prelude `defn`s** in the kotoba-clj subset itself — no new
codegen. Each takes a function argument and invokes it through the closure path
(`(f x)` → `CallValue` → `call_indirect`), iterating the heap vector with
`loop`/`recur` + `vec-nth`/`vec-conj!`.

Added to `PRELUDE`: `map`, `mapv`, `map-indexed`, `filter`, `filterv`, `remove`,
`keep`, `reduce` (2- and 3-arity), `reduce-kv`, `range` (1- and 2-arity), `some`,
`every?`, `not-any?`, `into`, `comp`, `partial`. `comp`/`partial` *return*
closures (`(fn [x] (f (g x)))`), exercising closure construction from inside the
prelude. Output vectors are pre-sized to the input count (exact for `map`, an
upper bound for `filter`/`remove`/`keep`) because `vec-conj!` does not grow.

Because the prelude now always contains `call_indirect`, **every** compiled
module needs a funcref table to exist (an indirect call to a missing table is a
validation error). Codegen therefore emits the table whenever the program
contains any `CallValue` *or* any lifted closure (`needs_table = has_indirect ||
!table_funcs.is_empty()`), and `collect_call_value_arities` pre-creates the
`(N+1)×i64 → i64` function types that `call_indirect` needs even when no `defn`
of that arity exists.

### Honest scope / known limits

`reduce` with no init over an empty coll calls `(f)` (Clojure semantics) which
traps on a binary reducer — caller's bug, fails cleanly. `into`/`conj!` onto a
fixed-capacity literal vector can overflow (pre-existing `vec-conj!` footgun —
vectors don't auto-grow); pre-size with `vec-make`. `apply` (dynamic arity),
multi-collection `map`, and lazy seqs are not provided. Remaining for full
langgraph-clj: protocols / `defrecord` dispatch.

Verification: `cargo test -p kotoba-clj --features run,component` green incl. the
new 16-test `tests/hofs.rs` (map→filter→reduce chains, reader-macro callbacks,
captured-variable callbacks, `comp`/`partial` returning closures, `range`,
`some`/`every?`/`keep`, `map-indexed`); clippy clean; no regressions across the
component/kqe/pregel suites that compile with the now-table-bearing prelude.

---

## Coverage batch — clojure.core stdlib + iteration sugars (2026-06-21)

Status: **Accepted.** Crate: `crates/kotoba-clj` (`tests/coverage.rs`, 16 tests).

Broadens Clojure-language coverage with **no new codegen path or runtime node** —
everything is either a pure-subset `PRELUDE` function (compiled through the
existing vec/map + closure-table machinery) or an AST desugar into existing
special forms.

**New special forms (`ast.rs` desugar):**

| form | desugars to |
|------|-------------|
| `(while test body…)` | `(loop [_ 0] (if test (do body… (recur 0)) 0))` |
| `(dotimes [i n] body…)` | `(let [_n n] (loop [i 0] (if (< i _n) (do body… (recur (+ i 1))) 0)))` |
| `(doseq [x coll] body…)` | `vec-count`/`vec-nth` walk in a `loop` (single binding; needs the prelude) |
| `(if-some [x e] t e?)` / `(when-some [x e] body…)` | alias `if-let`/`when-let` (nil≡0≡falsy in the i64 model) |

**New `PRELUDE` fns** (all output containers pre-sized; `vec-conj!`/`map-assoc!`
never grow): `take` `drop` `take-while` `drop-while` `butlast` `take-last`
`reverse` `concat` `repeat` `interpose` `interleave` `partition` `vec-contains?`
`distinct` `sort` `sort-by` `vec-swap!` `merge` `merge-with` `select-keys`
`zipmap` `get-in` `update` `complement` `juxt` `fnil` `max-key` `min-key`; plus
`vector` arity extended 4→8.

**Honest limits** (the i64 / mutable-bump model, unchanged): `distinct` /
`vec-contains?` compare scalars by value but collection/string handles by
identity; map fns assume **string keys** (the `str-eq?` contract); `sort` is
O(n²) selection sort; there is still no number tower (i64 only), no lazy seqs,
no persistent-immutable structures, and no dead-code elimination (every prelude
fn is emitted, so a prelude-on module grew ~5.5 KB → ~8.7 KB — negligible for
agents, a DCE target later).

Verification: `cargo test -p kotoba-clj` → **209 passed / 0 failed** (193 prior +
16 new); a combined end-to-end program (`sort`+`take`+`reduce`+`merge`+`dotimes`)
runs to the same result on **both** wasmtime and V8.
