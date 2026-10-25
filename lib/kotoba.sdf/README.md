# kotoba-lang/sdf

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-sdf` Rust crate
(`kami-sdf/src/lib.rs`, 528 lines; deleted from `kotoba-lang/kami-engine` in PR #82,
"Remove Rust workspace from kami-engine") as part of the **clj-wgsl migration**
(ADR-2607010930, `com-junkawasaki/root`).

## Status

Restored. `src/sdf.cljk` ports the full crate 1:1 as pure data + pure functions:

- SDF primitives (sphere / box / cylinder / capsule / torus) as signed-distance functions.
- A CSG tree (union / difference / intersection / smooth-union / density-field) that
  evaluates to a `{:distance d :color [r g b a]}` sample at any point.
- An affine transform representation (3x3 + translation, replacing `glam::Mat4`) with
  a cheap 3x3 cofactor inverse.
- A minimal local dense-voxel rasterizer (`sample-sdf`) that replaces the deleted
  crate's `kami_voxel::VoxelVolume` dependency with an in-namespace sparse voxel map,
  keeping this repo zero-dep.
- A hand-rolled recursive-descent JSON parser and an SDF JSON-LD dialect parser
  (`@type`/`pos`/`rot`/`scale`/`color`/`$ref`+`defs`) — no external JSON library.

All 8 original Rust `#[test]`s are ported 1:1 to `test/sdf_test.cljk`, plus the
namespace-loads smoke test — **9 tests / 17 assertions, 0 failures**.

Native execution (wgpu / wasmtime / wasmi) stays substrate; this repo owns the CLJC
contracts / data interpreters / EDN IR for the domain.

## Develop

```bash
kbb -M:test
```
