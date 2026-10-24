# ADR 0001: Kotoba owns RTX fallback reservation metadata

- Status: accepted
- Date: 2026-07-20

## Decision

`src/kotoba/rtx_native.kotoba` is the only production source. The former CLJC
constants are exposed as explicitly typed, zero-argument Kotoba getters. The
two compatibility targets use separate getters, avoiding an ambient or
unbounded host collection ABI. `activated?` explicitly returns `:bool`; it must
not inherit the default `:i64` function contract.

The repository contains reservation metadata, not an RTX renderer. Kami owns
future 3D/rendering providers; Kotoba owns this portable policy declaration and
its safe target artifacts.

## Runtime and verification

Production compiles to restricted JavaScript or typed Wasm and has no JVM or
ClojureScript runtime dependency. JVM Clojure remains build/test tooling only.
Reference, JavaScript, and independently instantiated Wasm must return the same
exact strings and boolean. CI rejects production `.clj`, `.cljc`, and `.cljs`.

Wasm byte identity is not required. The contract is validation,
instantiability, typed ABI conformance, and observable semantic equality.


## Amendment — 2026-08-13: authority and load path are different things

The migration that this ADR records deleted `src/kotoba/rtx_native.cljk` and left only
`src/kotoba/rtx_native.kotoba`. A `.kotoba` file is on no Clojure classpath, so from that
commit onward `kotoba.rtx-native` could not be loaded by ANY runtime this workspace
ranks above the native path (`kotoba wasm` > `clojurewasm` > ClojureScript > nbb,
and the JVM below them). "Production `.clj`/`.cljc`/`.cljs` sources are forbidden"
was read as "delete the load path", and the two are not the same requirement.

`src/kotoba/rtx_native.cljk` is restored beside the `.kotoba`, and:

* **the `.kotoba` remains the sole semantic authority.** Nothing about the migration
  is reverted. The restored file is a load path, not a second design.
* **a parity gate holds the two equal.** `test/kotoba/rtx_native_parity_test.cljk` compiles the
  `.kotoba` here and runs it through the reference evaluator in the same JVM,
  asserting agreement value by value. Where agreement is impossible it says so in a
  named test rather than dropping the case from the comparison.
* **`kotoba-lang/compiler` moved from `:deps` to the `:test` alias.** A consumer that
  requires the `.cljc` must not drag a compiler in behind it. `kotoba-lang/css`,
  `/dsl-core`, `/async` and `/postfx` set the same boundary.
* **`production-source-authority` is narrowed, not deleted.** `src/` is exactly two
  files. A third file, or a second `.cljc`, is still a fork of the authority and
  still fails.

**Semantics: verbatim.** The restored file is `c5e3c158^` unchanged, `activated?`
included — it is `false` on both sides and is the one export that is a function on
both sides, so it is the one like-for-like comparison here. The named divergence is
that `nv-compat-targets` is a vector here and two positional exports
(`nv-compat-primary`, `nv-compat-secondary`) in the guest.

**Removal condition.** The `.cljc` comes out when consumers have a load path that does
not require it — for the native route, ADR-2607279200 W4 in `com-junkawasaki/root`.
Until then, removing it is not a step of the migration; it is an outage.

Recorded in `com-junkawasaki/root` as ADR-2608134800, which follows ADR-2608130900
(`dsl-core`, `async`) and ADR-2608133600 (`postfx`, `cartpole-math`).
