# ADR 0001: Kotoba owns the cartpole source

- Status: accepted
- Date: 2026-07-20

## Decision

`src/kotoba/cartpole_math.kotoba` is the sole production source for cartpole
physics. The former `kami.cartpole-math` CLJC oracle and its Kotoba facade are
removed. `kami` remains the engine/domain layer; this repository supplies a
language-owned scalar physics kernel that an engine may call.

The source compiles with `kotoba-lang/compiler` to restricted JavaScript and
typed Wasm. JVM Clojure is permitted only as a build/test host. ClojureScript is
not a production compiler or runtime dependency.

## Safety and verification

- Configuration and state cross the public ABI as bounded `:vector-f64`
  values; action and each component result are explicitly `:f64`.
- Force is deterministically clamped before integration.
- Bounded Kotoba trigonometric operations enforce the language floating-point
  policy instead of importing host `Math.sin` or `Math.cos`.
- Reference, JavaScript, and Wasm outputs must agree semantically for canonical
  and non-canonical inputs, including an input that exercises force clamping.
- Short vectors and forged Wasm `externref` values must be rejected rather than
  being interpreted as partially valid physics state.
- Wasm must validate and instantiate. Binary byte identity is not required;
  only the fleet's representative structured fixture remains a byte sentinel.
- CI rejects any production `.cljc` source under `src`.

## Consequences

The generic CLJC map/vector facade and JVM-only output hashing are no longer
part of production. Hosts assemble the four scalar outputs into their preferred
state representation. A future structured f64 ABI may add a convenience export
without weakening the scalar contract.

## Amendment 2026-08-13 — authority and load path are separated

`src/kotoba/cartpole_math.kotoba` remains the sole SEMANTIC authority for the
physics. It is not reverted and no safety property above is withdrawn.

What is corrected is the last bullet of "Safety and verification": **"CI rejects any
production `.cljc` source under `src`."** That rule did not move `kami.cartpole-math`
to Kotoba; it deleted the only way any Clojure runtime can load it. `.kotoba` is not
loadable by the JVM, nbb or ClojureScript.

`kotoba-lang/webgpu` requires `[kami.cartpole-math :as cm]` from
`test/compute_golden_test.clj` and `scripts/gen_compute_golden.clj`, and pins this
repo at `7c6cb307` — **the migration commit itself**. So this consumer was not
protected by a stale pin the way `kotoba-lang/postfx`'s was: it broke the day the
migration landed, and stayed broken for 24 days, because each repo's CI only ever
looks at its own tree. Measured 2026-08-13, before this change:

    Execution error (FileNotFoundException) at compute-golden-test/eval2859
    Could not locate kami/cartpole_math__init.class, kami/cartpole_math.clj
    or kami/cartpole_math.cljc on classpath.

So:

* `src/kotoba/cartpole_math.kotoba` — the semantic authority. Bounded typed ABI,
  deterministic clamping, bounded trigonometry, reference/JS/Wasm conformance: all
  unchanged.
* `src/kami/cartpole_math.cljk` and `src/kotoba/cartpole_math.cljk` — the LOAD PATH,
  restored from `7c6cb307^`. Held to the authority by
  `test/cartpole_math_parity_test.cljk`, which compiles the `.kotoba` and runs it
  through the KIR interpreter in this same JVM (the shape `kotoba-lang/css`,
  `/dsl-core`, `/async` and `/postfx` use; ADR-2608130900 in com-junkawasaki/root).

`source-and-artifact-authority` is NARROWED, not deleted: `src/` holds exactly these
two `.cljc` files. A third would be a fork of the authority with nothing asserting
agreement, and is still refused. `kotoba-lang/compiler` moves from `:deps` to the
`:test` alias so consumers do not drag a compiler in behind the `.cljc`; `:lint` now
covers `src` as well as `test`.

Three things the parity test states rather than papers over:

* The surfaces are shaped differently ON PURPOSE. The guest exports four SCALAR
  functions because its typed ABI carries `:f64`; `step` returns the assembled
  4-vector. The asserted relation is exactly the "hosts assemble the four scalar
  outputs" sentence in Consequences above.
* Agreement is to **1.0e-13, not bit-identity**. The guest uses bounded
  `f64-sin-bounded` / `f64-cos-bounded` instead of host `Math.sin` / `Math.cos` —
  deliberately, per Safety above — and associates the multiplications differently.
  The tolerance is this repo's own: `cartpole-math-test` already compares the guest
  to a Clojure oracle at exactly 1.0e-13.
* `output-bytes` / `output-hash` have **no guest counterpart at all** and cannot be
  parity-tested: the guest has no bytes, no float formatting and no SHA-256. They
  are not therefore untested — the parity test pins the exact hex
  `b26f67a139ace0c4af23c5cfd507e5db9922edb6ccd22f600d956eba4276dfc9` that
  `kotoba-lang/webgpu`'s committed `fixtures/cartpole-compute-golden.json` depends
  on, so a serialisation change fails HERE instead of in that repo. Both functions
  are now guarded with `#?(:clj …)`, which is honest about a JVM-only surface the
  `.cljc` extension had been claiming was portable. The physics is portable.

REMOVAL CONDITION for the two `.cljc` files: when consumers have a load path that
does not require a `.cljc` — for the native route, ADR-2607279200 W4. Until then,
deleting them is not a step of the migration, it is an outage.
