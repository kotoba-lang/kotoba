# kotoba-lang/vegetation

`src/vegetation_golden.kotoba` is the policy-v7 safety qualification slice
for distance-based LOD, XZ distance, patch-range rejection, and scalar biome
placement eligibility. The test suite compares the existing CLJC domain
behavior with the Kotoba reference executor, restricted JavaScript, and typed
Wasm without host capabilities.

General instance collections, sorting, patch construction, mesh generation,
and GPU instance buffers remain CLJC until Kotoba has a structured f64
collection ABI. Deterministic scatter placement also remains an oracle until
the xorshift32 wrapping/shift profile is qualified.

Zero-dep portable `.cljc` — restored from the legacy `kami-vegetation` Rust crate
(`kotoba-lang/kami-engine`, deleted in PR #82 "Remove Rust workspace from kami-engine")
as part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

Decima-style procedural vegetation: taxonomy-driven `mesh-from-profile`, Poisson-disk
placement, and distance-based LOD/culling for GPU instancing. Pure data + pure functions
throughout — no IO, no GPU dispatch.

## Modules

Restored from the original 8-file Rust module layout (1530 lines total), one CLJC
namespace per module:

| Namespace                | Restored from | Purpose |
|---------------------------|---------------|---------|
| `vegetation.taxonomy`     | `taxonomy.rs` (489 lines) | Botanical classification (division / growth-habit / leaf-arrangement / leaf-shape / canopy-shape) → `TaxonomicProfile` generation parameters; 7-species preset catalog (grass, fern, palm, conifer, bush, cactus, moss); `RemoteCatalog` + a minimal zero-dependency JSON reader for the `seibutsu.renderProfile` wire format. |
| `vegetation.species`      | `species.rs` (152 lines) | Species placement rules (height/slope/splatmap-affinity/density/min-distance) + render params (scale, wind sway, color gradient) for the 5-species GPU atlas (grass, fern, palm, conifer, bush). |
| `vegetation.instance`     | `instance.rs` (26 lines) | Per-plant GPU instance data (8-float / 32-byte layout: position, scale, rotation, species, wind-phase, color-tint). |
| `vegetation.lod`          | `lod.rs` (44 lines) | Distance-based LOD tier classification (`:detail`/`:billboard`/`:culled`) per species. |
| `vegetation.cull`         | `cull.rs` (244 lines) | Distance culling + closest-N budget selection; Stage-5 spatial-cell patch clustering (`build-patches`/`patches-in-range`/`cull-with-patches`) for the N > ~10k scaling case. |
| `vegetation.mesh`         | `mesh.rs` (368 lines) | `mesh-from-profile`: taxonomy-profile-driven procedural mesh generation (7 canopy-shape generators — blade/fan/radial/cone/dome/column/carpet — sharing quad/tapered-blade/trunk-cross vertex pushers). |
| `vegetation.placement`    | `placement.rs` (189 lines) | Poisson-disk dart-throwing scatter placement over terrain, with height/slope/splatmap biome filtering; deterministic xorshift32 PRNG ported bit-for-bit from the original Rust `Rng`. |
| `vegetation`               | `lib.rs` (18 lines) | Root namespace re-exporting the public API, mirroring the original `pub use` surface. |

`vegetation.placement` intentionally does **not** depend on `kami-terrain`'s
`Heightmap`/`Splatmap` types (this crate is zero-dependency); it instead takes a plain
CLJC heightmap/splatmap shape (`{:width :depth :sample (fn [hx hz]) :normal (fn [gx gz])}`
/ `{:width :data [{:weights [...]} ...]}`) that mirrors the original call sites 1:1.

## Status

Restoration complete. All original Rust `#[test]`s ported 1:1 to
`test/vegetation_test.cljk` (plus the namespace-loads smoke test and one extra
Poisson-disk minimum-separation coverage test) — **25 tests / 180,986 assertions,
0 failures, 0 errors**.

## Develop

```bash
kbb -M:test
```
