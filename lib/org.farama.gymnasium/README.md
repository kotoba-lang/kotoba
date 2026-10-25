# kotoba-lang/cartpole-wasm

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-cartpole-wasm` Rust crate
(`kotoba-lang/kami-engine`, 86-line `src/lib.rs`, deleted in PR #82 "Remove Rust workspace from
kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

## What this is

The deleted `kami-cartpole-wasm` crate was a thin `wasm-bindgen` wrapper (`CartpoleHandle`)
exposing `kami_shugyo::CartpoleEnv` (a separate crate, out of scope here) to JavaScript, as a
demonstrator for Phase C of ADR-2605261800 (KAMI canonical Rust -> wasm32 -> JS/Isaac-Sim-style
RL env). The crate's own `lib.rs` contained no cartpole physics itself — it was pure
wasm-bindgen boundary glue delegating to `kami_shugyo`.

To preserve real computational content rather than just glue, `src/cartpole_wasm.cljk` ports
the classic Barto/Sutton/Anderson cartpole equations of motion (the same dynamics
`kami_shugyo::CartpoleEnv` implements) as pure, zero-dependency CLJC data + functions, matching
the original JS-facing API surface:

- `cartpole-reset seed` -> flattened `[x x-dot theta theta-dot]` (+ carried state map)
- `cartpole-step state force` -> flattened `[x x-dot theta theta-dot reward terminated? truncated?]` (+ next state map)
- `observation-dim` -> `4`, `action-dim` -> `1`
- `kami-cartpole-version` -> `"ADR-2605261800@R1.1"`

Mutating `&mut self` methods on `CartpoleHandle` became pure functions: `step-state` takes an
immutable state map and returns the next one, rather than mutating in place. A deterministic
seeded LCG PRNG replaces the original seeded reset. Native execution (wgpu / wasmtime / wasmi /
actual PhysX / Isaac Sim bridging) stays substrate; this namespace owns the CLJC contracts /
pure dynamics / EDN IR for the domain.

## Tests

`test/cartpole_wasm_test.cljk` ports the single original Rust `#[test] handle_lifecycle`
(reset returns a 4-vector, step returns a 7-vector) plus additional coverage of the ported
dynamics (determinism, reset perturbation bounds, force response, termination on tip-over,
truncation at the step budget, dim/version constants) and the namespace smoke test.

9 tests, 15 assertions, 0 failures, 0 errors.

## Develop

```bash
kbb -M:test
```
