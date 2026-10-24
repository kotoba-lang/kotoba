(ns scad
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-scad Rust crate
  (`kami-scad/src/lib.rs`, deleted in kotoba-lang/kami-engine PR #82 \"Remove Rust
  workspace from kami-engine\") as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  Purpose: OpenSCAD subset parser + CSG evaluator. Original pipeline was
  `OpenSCAD code -> ScadEntity[] -> SDF -> VoxelVolume -> Mesh/GLB`; this root
  namespace re-exports the portable, self-contained pieces (mirrors the
  original `pub use csg::cylinder_mesh; pub use evaluator::{...}; pub use
  parser::{...};` re-export block):

  - `scad.parser/parse`       — OpenSCAD source -> AST (`ScadNode` equivalent)
  - `scad.evaluator/evaluate` — AST -> flattened renderable entities (`ScadEntity`)
  - `scad.csg/cylinder-mesh`  — cylinder/cone mesh geometry

  NOT ported: `scad_to_glb`, `scad_to_mesh`, `entities_to_sdf` (the full
  pipeline functions from the original `lib.rs`) and `cylinder_loaded` (from
  `csg.rs`). All of these glue the pure logic above to unported sibling
  crates (`kami-sdf`, `kami-mesher`, `kami-gltf`, `kami-render`) and are out of
  scope for this zero-dependency restoration — only the parser/evaluator/CSG
  geometry logic itself is restored."
  (:require [scad.parser :as parser]
            [scad.evaluator :as evaluator]
            [scad.csg :as csg]))

(def parse
  "OpenSCAD source -> AST (vector of tagged maps). See `scad.parser/parse`."
  parser/parse)

(def evaluate
  "OpenSCAD source -> vector of renderable `ScadEntity` maps.
  See `scad.evaluator/evaluate`."
  evaluator/evaluate)

(def cylinder-mesh
  "Cylinder/cone mesh geometry. See `scad.csg/cylinder-mesh`."
  csg/cylinder-mesh)
