# kotoba-lang/terrain

`src/terrain_golden.kotoba` is the safety-first policy-v7 qualification slice
for canonical cosine-interpolated value noise, four-octave FBM/height shaping,
and wind-derived Gerstner wave parameters. Tests compare the existing CLJC
domain oracle with the Kotoba reference executor, restricted JavaScript, and
typed Wasm, without host capabilities or host transcendental imports.

The canonical noise slice begins after the existing i32 lattice hash values;
general procedural noise remains CLJC until Kotoba has qualified i32 wrapping
multiply/shift semantics. Structured heightmaps and water meshes likewise
remain CLJC until a structured f64 collection ABI is available.

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-terrain` Rust crate
(deleted in `kotoba-lang/kami-engine` PR #82, "Remove Rust workspace from kami-engine") as
part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

Decima-style (Guerrilla Games, Horizon Zero Dawn) heightmap terrain engine: procedural
generation (value noise + FBM), splatmap material blending, chunk-based mesh generation with
LOD, Gerstner-wave water surfaces, and biome presets. Pure data + pure functions throughout —
no IO, no GPU. Native execution (wgpu / wasmtime / wasmi) stays substrate.

## Status

Restored. All 7 original Rust modules (913 lines total) are ported 1:1 to CLJC:

| Module | Source (`kami-terrain/src/`) | Purpose |
| --- | --- | --- |
| `terrain.cljc` | `lib.rs` (20 lines) | Root namespace; re-exports the public surface of the sibling `terrain.*` namespaces |
| `terrain/noise.cljc` | `noise.rs` (82 lines) | Hash-based value noise (patent-safe, not Perlin) + FBM (Fractal Brownian Motion) |
| `terrain/heightmap.cljc` | `heightmap.rs` (135 lines) | 2D elevation grid generated via FBM; bilinear sampling; central-difference normals |
| `terrain/biome.cljc` | `biome.rs` (170 lines) | Biome presets (plains/quarry/desert/tundra): FBM params, splat thresholds, material palettes |
| `terrain/chunk.cljc` | `chunk.rs` (128 lines) | Chunked triangle mesh generation from heightmap + splatmap, with LOD via vertex stride |
| `terrain/splatmap.cljc` | `splatmap.rs` (107 lines) | Per-vertex material blend weights (grass/rock/sand/snow) from height + slope rules |
| `terrain/water.cljc` | `water.rs` (271 lines) | Gerstner wave parameter sets (fixed defaults or derived from wind) + flat water grid mesh |

All 14 original Rust `#[test]`s are ported 1:1 to `test/terrain_test.cljk` (same assertions,
translated to `clojure.test`), plus the original scaffold's `namespace-loads` smoke test —
**15 tests / 11097 assertions, 0 failures.**

Reader conditionals (`#?(:clj ... :cljs ...)`) isolate the handful of JVM/JS math-primitive
divergences (`Math/sqrt` vs `js/Math.sqrt`, 32-bit wrapping multiply for the noise hash, etc.)
so the rest of the code is platform-neutral CLJC, portable to both JVM Clojure and
ClojureScript.

## Develop

```bash
kbb -M:test
```
