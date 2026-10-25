# kotoba-lang/nerf

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-nerf` Rust crate
(`kami-nerf/src/lib.rs`, 144 lines, deleted in `kotoba-lang/kami-engine` PR #82 "Remove
Rust workspace from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

## What this is

Loads a pre-trained NeRF (Neural Radiance Field) density grid — a 3D scalar field of
density values plus an optional co-located RGB color field — and samples it into a
sparse voxel volume, trilinear-interpolating density at each voxel center and keeping
cells above a threshold. Pure data + pure functions; no IO/GPU.

The original Rust crate depended on `kami-voxel` for its `VoxelVolume`/`Voxel` output
type. That crate has not yet been restored as a CLJC dependency, so `src/nerf.cljk`
ports a minimal self-contained voxel volume representation (a sparse `[x y z] -> voxel`
map) sufficient to satisfy `to-volume`'s contract, rather than introducing a hard
dependency.

Public API: `make-density-grid`, `with-colors`, `sample`, `sample-color`, `to-volume`,
plus the minimal volume helpers `new-dense-volume`, `set-voxel`, `count-filled`, and
portable Vec3 math helpers (`v-sub`, `v-add`, `v-div`, `v-scale`, `v-length`, `v-zero`,
`v-splat`, `clamp`, `fract`).

## Status

Restored. Both original Rust `#[test]`s (`sphere_density`, `with_colors`) are ported
1:1 to `test/nerf_test.cljk`, plus a namespace-loads smoke test — 3 tests / 4 assertions,
0 failures.

## Develop

```bash
kbb -M:test
```
