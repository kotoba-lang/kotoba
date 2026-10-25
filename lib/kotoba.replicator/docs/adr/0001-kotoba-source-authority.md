# ADR 0001: Kotoba source authority

## Status

Accepted.

## Decision

`src/kotoba/replicator.kotoba` is the sole production source for the
Replicator path-reservation metadata. Production `.clj`, `.cljc`, and `.cljs`
sources are forbidden.

This repository does not implement synthetic-data generation. Randomization,
rendering, sensors, GPU execution, and NVIDIA-compatible providers remain
gated Kami responsibilities. The metadata contract exposes closed typed string
getters and is executed through the reference evaluator, restricted
JavaScript, and instantiated typed Wasm.

Compatibility is semantic and ABI-based, not Wasm byte identity. The JVM is
permitted only as compiler/test infrastructure.


## Amendment — 2026-08-13: authority and load path are different things

The migration that this ADR records deleted `src/kotoba/replicator.cljk` and left only
`src/kotoba/replicator.kotoba`. A `.kotoba` file is on no Clojure classpath, so from that
commit onward `kotoba.replicator` could not be loaded by ANY runtime this workspace
ranks above the native path (`kotoba wasm` > `clojurewasm` > ClojureScript > nbb,
and the JVM below them). "Production `.clj`/`.cljc`/`.cljs` sources are forbidden"
was read as "delete the load path", and the two are not the same requirement.

`src/kotoba/replicator.cljk` is restored beside the `.kotoba`, and:

* **the `.kotoba` remains the sole semantic authority.** Nothing about the migration
  is reverted. The restored file is a load path, not a second design.
* **a parity gate holds the two equal.** `test/kotoba/replicator_parity_test.cljk` compiles the
  `.kotoba` here and runs it through the reference evaluator in the same JVM,
  asserting agreement value by value. Where agreement is impossible it says so in a
  named test rather than dropping the case from the comparison.
* **`kotoba-lang/compiler` moved from `:deps` to the `:test` alias.** A consumer that
  requires the `.cljc` must not drag a compiler in behind it. `kotoba-lang/css`,
  `/dsl-core`, `/async` and `/postfx` set the same boundary.
* **`production-source-authority` is narrowed, not deleted.** `src/` is exactly two
  files. A third file, or a second `.cljc`, is still a fork of the authority and
  still fails.

**Semantics: verbatim.** The restored file is `d875a29e^` unchanged. Every value the
guest exports is byte-identical to the constant it replaced, so no reconciliation was
needed — but that was established by diffing and is now asserted, not assumed. Two
divergences are named in the parity test: constants cross as nullary functions because
Kotoba has no top-level value bindings, and the `status` map has no guest counterpart
at all (the migration flattened the record away), so it is pinned to the four
guest-backed scalars instead of being left unchecked.

**Removal condition.** The `.cljc` comes out when consumers have a load path that does
not require it — for the native route, ADR-2607279200 W4 in `com-junkawasaki/root`.
Until then, removing it is not a step of the migration; it is an outage.

Recorded in `com-junkawasaki/root` as ADR-2608134800, which follows ADR-2608130900
(`dsl-core`, `async`) and ADR-2608133600 (`postfx`, `cartpole-math`).
