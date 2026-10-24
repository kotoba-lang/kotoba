# ADR 0001: Kotoba owns the quarry configuration contract

## Decision

`src/kami_app_quarry_walk.kotoba` is the sole production language source. Its
exports are closed, typed scalar configuration values. JVM Clojure is only a
test/compiler host and is not a production runtime.

Rendering, terrain streaming, input handling, WebGPU, physics, and game-loop
orchestration remain capability-gated Kami providers. This module cannot invoke
those effects; it only supplies admitted configuration across that boundary.

Conformance is checked by observable values, declared types, effects, and ABI
behavior in the reference evaluator, restricted JavaScript, and instantiated
typed Wasm. Generated Wasm bytes are intentionally not required to be equal.

## Consequences

- `.cljc`, `.clj`, and `.cljs` are rejected under `src`.
- Configuration maps are decomposed into typed exports, avoiding an ambient,
  extensible host-data boundary.
- Any future device or game-engine operation requires an explicit Kami
  capability and a separate admission decision.


## Amendment — 2026-08-13: authority and load path are different things

The migration that this ADR records deleted `src/kami_app_quarry_walk.cljk` and left only
`src/kami_app_quarry_walk.kotoba`. A `.kotoba` file is on no Clojure classpath, so from that
commit onward `kami-app-quarry-walk` could not be loaded by ANY runtime this workspace
ranks above the native path (`kotoba wasm` > `clojurewasm` > ClojureScript > nbb,
and the JVM below them). "Production `.clj`/`.cljc`/`.cljs` sources are forbidden"
was read as "delete the load path", and the two are not the same requirement.

`src/kami_app_quarry_walk.cljk` is restored beside the `.kotoba`, and:

* **the `.kotoba` remains the sole semantic authority.** Nothing about the migration
  is reverted. The restored file is a load path, not a second design.
* **a parity gate holds the two equal.** `test/kami_app_quarry_walk_parity_test.cljk` compiles the
  `.kotoba` here and runs it through the reference evaluator in the same JVM,
  asserting agreement value by value. Where agreement is impossible it says so in a
  named test rather than dropping the case from the comparison.
* **`kotoba-lang/compiler` moved from `:deps` to the `:test` alias.** A consumer that
  requires the `.cljc` must not drag a compiler in behind it. `kotoba-lang/css`,
  `/dsl-core`, `/async` and `/postfx` set the same boundary.
* **`production-source-authority` is narrowed, not deleted.** `src/` is exactly two
  files. A third file, or a second `.cljc`, is still a fork of the authority and
  still fails.

**Semantics: verbatim.** The restored file is `b55cf842^` unchanged. Two divergences
are named. First, the guest has no nested configuration: the migration flattened the
whole `app-config` tree into 17 scalar exports, so the parity test rebuilds the nested
value out of guest calls rather than comparing shapes. Second — and this one is a real
gap, not a representation difference — `:label "quarry-walk"` HAS NO GUEST EXPORT AT
ALL. It is pinned literally in a test named for the gap, so it cannot pass as
parity-checked.

**Removal condition.** The `.cljc` comes out when consumers have a load path that does
not require it — for the native route, ADR-2607279200 W4 in `com-junkawasaki/root`.
Until then, removing it is not a step of the migration; it is an outage.

Recorded in `com-junkawasaki/root` as ADR-2608134800, which follows ADR-2608130900
(`dsl-core`, `async`) and ADR-2608133600 (`postfx`, `cartpole-math`).
