# kotoba-lang/mesher

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-mesher` Rust crate
(deleted in the kotoba-lang Rust removal) as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

## Status

Restored. Ports `kami-mesher/src/lib.rs` (813 lines) and `kami-mesher/src/mc_tables.rs`
(307 lines) — 1120 lines total, recovered from `kotoba-lang/kami-engine` at commit
`a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa` (pre-deletion) — to zero-dependency
portable `.cljc`:

- `src/mesher/mc_tables.cljk` — the standard Paul Bourke / Lorensen-Cline Marching
  Cubes lookup tables (256-entry edge table, 256×16 triangle table, 12-entry
  edge-vertex table), transcribed faithfully as CLJC data.
- `src/mesher.cljk` — Marching Cubes isosurface mesh generation from a scalar
  density (signed-distance) field (`sdf-to-mesh`, `sdf-to-colored-mesh`,
  `split-mesh-by-color`), plus a dense-voxel-volume face-culling mesher
  (`marching-cubes`, `greedy-mesh-volume` — legacy names kept for API parity).

Ledger class `:port-to-WGSL-compute` — restored here as a plain interim CLJC
implementation (pure data + pure functions, no GPU/WGSL, no IO) per owner decision,
standing in for what the migration ledger originally classified as WGSL-compute-authored
logic. Portable to both JVM Clojure and ClojureScript via `#?(:clj ... :cljs ...)`
reader conditionals where platform math (`Math/sqrt` etc.) is needed.

5 of the original Rust `#[test]`s were ported 1:1 (+1 smoke test) — 6 tests / 13
assertions, 0 failures. Two tests were not ported because they depend on external,
still-Rust crates out of scope for this restoration (`kami_sdf`'s JSON-LD SDF parser,
and `kami_voxel`'s sparse/octree `VoxelVolume` variants — see `test/mesher_test.cljk`
docstring for details); only the dense voxel-volume representation is restored here.

Part of the clj-wgsl migration (ADR-2607010930, `com-junkawasaki/root`).

## Develop

```bash
kbb -M:test
```
