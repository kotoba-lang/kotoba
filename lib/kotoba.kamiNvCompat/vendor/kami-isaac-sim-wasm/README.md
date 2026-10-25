# vendor/kami-isaac-sim-wasm

Vendored `wasm-pack build --target nodejs` output of the
`kami-isaac-sim-wasm` crate (`kotoba-lang/kami-engine/kami-isaac-sim-wasm`),
which wraps `kami-genesis::IsaacWorld` (Featherstone RNEA/CRBA dynamics + PD
control, 208 tests) as a JS-callable wasm-bindgen module.

**Status**: proof-of-bridge only (ADR-2607011300 follow-up). This vendored
copy exists so `test/isaac-sim-wasm-bridge.smoke.test.ts` can prove the
Rust → wasm32 → Node round-trip actually works. It is **not yet wired into**
`src/isaac-sim.ts` / `src/e7m-sim/` — those still run the from-scratch
TypeScript Featherstone implementation (`src/dynamics/`, `src/controllers/`,
`src/actions/`). Swapping them to consume this WASM module instead requires
deciding how to reconcile WASM's async instantiation with the existing
486-test synchronous API (`new Articulation(...)` / `new World(...)` are not
`async` today).

## Regenerating

From `kotoba-lang/kami-engine/kami-isaac-sim-wasm/`:

```bash
wasm-pack build --target nodejs --out-dir pkg
cp pkg/kami_isaac_sim_wasm_bg.wasm pkg/kami_isaac_sim_wasm.js \
   pkg/kami_isaac_sim_wasm.d.ts pkg/kami_isaac_sim_wasm_bg.wasm.d.ts \
   <this-directory>/
```

Long-term this should become a real npm dependency (publish the wasm-pack
output as an npm package) instead of a vendored copy.
