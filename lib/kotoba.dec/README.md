# kotoba-lang/dec

Zero-dep portable `.cljc` — restored from the legacy `kami-dec/src/lib.rs` Rust crate
(1412 lines, `kotoba-lang/kami-engine`, deleted in PR #82 "Remove Rust workspace from
kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

## What this is

Discrete Exterior Calculus (DEC) on a voxel cubical complex — the v3 physics prototype
that expresses field dynamics (heat/smoke diffusion, incompressible flow, vacuum Maxwell,
vorticity confinement) via a small shared vocabulary of `d` (exterior derivative), `*`
(Hodge star, deferred/implicit on the flat unit-spacing grid) and `Δ = *d*d + d*d*`
(Laplacian → 7-point stencil on 0-forms).

Ported: `scalar-field` / `edge-field` / `face-field` (sparse, chunked 0-/1-/2-forms),
`scalar-diffuse`, `emit-from`, trilinear sampling + semi-Lagrangian advection
(`scalar-advect-uniform` / `scalar-advect-field`), `d-0` (gradient) / `div` (divergence),
damped-Jacobi and 2-level-V-cycle multigrid Poisson solvers
(`solve-poisson-jacobi` / `solve-poisson-multigrid`), Helmholtz divergence-free projection
(`project-divergence-free` / `project-divergence-free-mg`), `d-1` (curl) /
`curl-face-to-edge` (its adjoint), a Yee-leapfrog `maxwell` / `maxwell-step` /
`maxwell-energy` integrator, and Fedkiw-style `vorticity-confine`.

This is a plain, zero-dep portable CLJC interim implementation standing in for what the
migration ledger classifies as `:port-to-WGSL-compute` ("chunk management + dispatch;
field ops → WGSL compute") — per owner decision it is ported here as pure CLJC data +
pure functions rather than real WGSL compute shaders. Native execution (wgpu / wasmtime /
wasmi) stays substrate.

## Status

Restoration complete. All 8 original Rust `#[test]`s ported 1:1 to `test/dec_test.cljk`
(plus a namespace-loads smoke test) — 10 tests / 78 assertions, 0 failures, 0 errors.

## Develop

```bash
kbb -M:test
```
