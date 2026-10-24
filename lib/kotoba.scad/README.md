# kotoba-lang/scad

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-scad` Rust crate
(deleted in `kotoba-lang/kami-engine` PR #82 "Remove Rust workspace from kami-engine")
as part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

## Status

Restored. Ports the OpenSCAD subset parser + CSG evaluator from the deleted Rust crate
(`kami-scad/src/{lib,parser,evaluator,csg}.rs`, 1173 lines) to pure, portable CLJC data
+ functions (JVM Clojure / ClojureScript compatible):

- `src/scad/parser.cljk` — hand-rolled tokenizer + recursive-descent parser for a small
  OpenSCAD subset (sphere/cube/cylinder primitives, translate/rotate/scale/color
  transform blocks, union/difference/intersection groups, zero-arg module def/call) into
  a `ScadNode`-equivalent AST of tagged maps.
- `src/scad/evaluator.cljk` — flattens the AST into a vector of renderable `ScadEntity`
  maps (`{:id :position :rotation :scale :primitive :color}`), tracking accumulated
  transform via a local, portable port of `glam::Mat4`/`Quat` (column-major 4x4 matrix,
  `to_scale_rotation_translation` decomposition, quaternion-from-rotation-matrix).
  Difference/intersection are evaluated as union (same Phase-1 visual-approximation
  simplification the original Rust carried — real boolean CSG mesh ops were a Phase-2
  TODO in the deleted crate).
- `src/scad/csg.cljk` — `cylinder-mesh`: Y-axis-aligned truncated-cone geometry
  (positions/normals/uvs/indices).
- `src/scad.cljk` — root namespace re-exporting `parse` / `evaluate` / `cylinder-mesh`.

**Not ported** (out of scope for a zero-dependency restoration): the original `lib.rs`
pipeline functions `scad_to_glb` / `scad_to_mesh` / `entities_to_sdf`, and
`csg.rs::cylinder_loaded`. These all glue the logic above to unported sibling Rust
crates (`kami-sdf`, `kami-mesher`, `kami-gltf`, `kami-render`) and have no CLJC
equivalent in this repo.

All 12 original Rust `#[test]`s that don't depend on those unported crates are ported
1:1 to `test/scad_test.cljk`, plus 1 namespace-load smoke test — **13 tests / 42
assertions, 0 failures**.

## Develop

```bash
kbb -M:test
```
