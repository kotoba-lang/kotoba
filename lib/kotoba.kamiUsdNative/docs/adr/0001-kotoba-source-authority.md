# ADR 0001: Kotoba source authority

## Status

Accepted.

## Decision

`src/usd_native.kotoba` is the sole production source for this contingent USD
fallback reservation. Production `.clj`, `.cljc`, and `.cljs` are forbidden.

The contract contains metadata only. USD parsing/composition, native code,
WebGPU, rendering, and device capabilities remain inactive Kami providers
until the external viability and Council gates are satisfied.

Closed typed string getters preserve every scalar and each member of the two
former string vectors. Tests execute them through the reference evaluator,
restricted JavaScript, and instantiated typed Wasm. Compatibility is semantic
and ABI-based, not Wasm byte identity.

The JVM is permitted only as compiler/test infrastructure.


## Amendment — 2026-08-13: authority and load path are different things

The migration that this ADR records deleted `src/usd_native.cljk` and left only
`src/usd_native.kotoba`. A `.kotoba` file is on no Clojure classpath, so from that
commit onward `usd-native` could not be loaded by ANY runtime this workspace
ranks above the native path (`kotoba wasm` > `clojurewasm` > ClojureScript > nbb,
and the JVM below them). "Production `.clj`/`.cljc`/`.cljs` sources are forbidden"
was read as "delete the load path", and the two are not the same requirement.

`src/usd_native.cljk` is restored beside the `.kotoba`, and:

* **the `.kotoba` remains the sole semantic authority.** Nothing about the migration
  is reverted. The restored file is a load path, not a second design.
* **a parity gate holds the two equal.** `test/usd_native/parity_test.cljk` compiles the
  `.kotoba` here and runs it through the reference evaluator in the same JVM,
  asserting agreement value by value. Where agreement is impossible it says so in a
  named test rather than dropping the case from the comparison.
* **`kotoba-lang/compiler` moved from `:deps` to the `:test` alias.** A consumer that
  requires the `.cljc` must not drag a compiler in behind it. `kotoba-lang/css`,
  `/dsl-core`, `/async` and `/postfx` set the same boundary.
* **`production-source-authority` is narrowed, not deleted.** `src/` is exactly two
  files. A third file, or a second `.cljc`, is still a fork of the authority and
  still fails.

**Semantics: verbatim.** The restored file is `e56fffc2^` unchanged. The divergence
worth naming is that this guest has no sequences: `nv-compat-targets` and
`supported-formats` were flattened into positional exports (`nv-compat-target-0/1/2`,
`supported-format-0/1/2`). The parity test compares element by element and pins each
length, so a fourth element cannot appear without a guest export behind it — but the
sequence itself has no counterpart, and the test says so.

**Removal condition.** The `.cljc` comes out when consumers have a load path that does
not require it — for the native route, ADR-2607279200 W4 in `com-junkawasaki/root`.
Until then, removing it is not a step of the migration; it is an outage.

Recorded in `com-junkawasaki/root` as ADR-2608134800, which follows ADR-2608130900
(`dsl-core`, `async`) and ADR-2608133600 (`postfx`, `cartpole-math`).
