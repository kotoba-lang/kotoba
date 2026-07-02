# ADR — `kotoba wasm` actually executes (JVM Clojure runtime, kgraph store)

- **Status**: Accepted, implemented
- **Date**: 2026-07-02
- **Related**: [`ADR-kotoba-wasm.md`](ADR-kotoba-wasm.md) (historical Rust
  `kotoba-clj` compiler-path design — superseded as an implementation, kept as
  a migration record per `README.md`'s "Legacy Rust crates ... have been
  removed" note), [`ADR-safe-capability-language.md`](ADR-safe-capability-language.md)

## Context

This repository's current tree is JVM Clojure only (`src/kotoba/*.clj`); the
Rust `kotoba-clj`/`kotoba-query`/... crates `ADR-kotoba-wasm.md` and
`CLAUDE.md`'s crate table describe were removed (see git history). The
surviving `kotoba.runtime`/`kotoba.launcher` slice already had a correct,
hand-rolled WASM MVP binary encoder (`kotoba.runtime/wasm-binary` — real
section layout, LEB128, imports/exports/memory/data segments) — but nothing
in the repository ever loaded and ran the bytes it produced. Every existing
`wasm-emit-*` test asserted byte SHAPE only (magic bytes, import/function
counts); `kotoba wasm emit` wrote a file and stopped there.

Separately, the host-import surface for the EAVT graph-store operations
(assert/retract/get-objects/query) was named `kqe` (Kotoba Query Engine) —
inherited from the old Rust crate naming, spelled out in `CLAUDE.md`. That
name reads as read-only, but the surface's own two write operations
(`kqe-assert!`/`kqe-retract!`) contradict it.

## Decision

1. **Actually execute emitted modules.** New `kotoba.wasm-exec` loads
   `wasm-binary`'s bytes with `com.dylibso.chicory` (a pure-JVM WebAssembly
   runtime — Maven dependency, no native toolchain, no wasmtime/wasmer
   process) and runs the exported `main`. Host imports are a thin
   `(Instance memory ptr/len) <-> EDN` adapter — the SAME `(module="kotoba",
   field)` ABI a browser or Cloudflare Worker host would implement, so this
   is a real proof of the wire contract, not a mock.
2. **New CLI verb: `kotoba wasm run <source>`.** Does what `wasm emit` does
   (check + emit) and then executes: `kgraph-*` imports run for real against
   a fresh per-invocation `kotoba.kgraph` store; every other declared import
   gets a trivial 0-returning stub (`wasm-exec/stub-host-function`, generated
   from the same `kotoba.runtime/host-imports` metadata), matching
   `kotoba.host-providers/default-handlers`' existing stub convention — so a
   valid program never fails to link for lack of a real native provider.
3. **Rename `kqe` → `kgraph`.** New pure namespace `kotoba.kgraph` (EAVT
   datom vector; `assert-datom`/`retract-datom`/`get-objects`/`query` — a
   small but real join-based Datalog matcher, no Rust dependency). The
   host-import contract, effect-op classification, and capability-kind
   registration were renamed to match in three sibling repos (single
   capability `"graph/kotoba"` covers all four ops, mirroring the existing
   `fs-read`/`fs-write` → `"fs/app-data"` pattern):
   - `kotoba-core-contracts` PR #1 — `capability_contract.edn`
     (`kgraph-assert!`/`kgraph-retract!`/`kgraph-get-objects`/`kgraph-query`,
     capability id 209)
   - `kotoba-selfhost-contracts` PR #1 — `safe_analyzer_facts.edn` effect-ops
   - `kotoba-lang` PR #10 — `capability_values.cljc` (`:host/graph-assert`,
     `:host/graph-retract`, `:host/graph-get-objects`, `:host/graph-query`)
   - this repo, PR #268 — `kotoba.runtime/op->kind`,
     `kotoba.host-providers/default-handlers` (0-stub, matching every other
     host op) + new `kgraph-handlers` (real, EDN-literal-argument handlers
     for exercising the store from the interpreter without going through
     WASM at all)

   `ADR-safe-capability-language.md`'s historical prose (describing the old
   Rust per-cid `kqe-assert!`/quad-store shape) is left as-is — it documents
   a design this repo's current tree never implements the same way, and
   rewriting history there would misattribute a shape (4-arg graph-cid/s/p/o
   calls) this JVM slice does not have.

## Consequences

- `kotoba wasm run` is a genuine compile → check → emit → **execute** round
  trip, verified without mocks: `kotoba.wasm-exec-test` runs a trivial
  no-import module and confirms its result matches the interpreter; runs the
  kgraph round trip (assert → emit → Chicory-execute → real host function →
  read the query result back out of guest linear memory) and confirms it
  matches what was asserted. `kotoba.launcher-test` repeats the same round
  trip through the actual CLI (`kotoba wasm run ... --json`). Manually:
  `clojure -M -m kotoba.launcher wasm run src/demo_kgraph.kotoba --policy
  src/demo_kgraph_policy.edn --json` → `"kotoba.wasm/value":9` (the real byte
  count `kgraph_query` wrote back).
- `kotoba.kgraph`'s store is in-memory and per-invocation (no persistence,
  no distribution, no Pregel/BSP, no CID-addressed graphs) — a minimal but
  real substrate for the host-import ABI, not a replacement for the historical
  Rust `kotoba-query`/`kotoba-datomic` design `ADR-kotoba-wasm.md` describes.
  Reviving durable/distributed graph storage, if wanted, is future work and
  should get its own ADR rather than retrofitting this one.
- `notify-show`/`clipboard-*`/`http-fetch`/`keychain-*`/`fs-*` remain
  0-returning stubs in both the interpreter (`default-handlers`) and
  `kotoba wasm run` (`stub-host-function`) — real native providers for those
  are unchanged/out of scope here.
- No browser or Cloudflare Worker host for this JVM-defined ABI exists yet in
  this repository; `kotoba.wasm-exec` proves the contract is real and
  runnable, which is the prerequisite for such a host, not the host itself.
