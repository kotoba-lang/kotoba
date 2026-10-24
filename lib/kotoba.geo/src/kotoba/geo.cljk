(ns kotoba.geo
  "kotoba.geo: GIS primitives — Web Mercator projection, tile math, raster
  tile mesh, billboard definitions, GeoJSON-ish line/polygon mesh
  generation.

  Ported from kami-engine/kami-geo (Rust, deleted from the working tree
  pre-commit; recovered from git history) into pure `.cljc`. No network/IO
  — see `90-docs/adr/2607010000-kotoba-runtime-sdk-cljc-migration.md`.

  Sub-namespaces (mirrors kami-geo's `pub mod` list in `lib.rs`):
  - `kotoba.geo.constants`  — extracted numeric constants (EDN-authority
    mirrored at `resources/kotoba/geo/constants.edn`)
  - `kotoba.geo.projection` — Web Mercator (EPSG:3857) lng/lat ⇄ world-px
    ⇄ tile-coord conversions
  - `kotoba.geo.tile`       — tile cache / LOD state machine (pure)
  - `kotoba.geo.mesh`       — tile quads, globe patches, GeoJSON
    line/polygon → mesh, ear-clipping triangulation
  - `kotoba.geo.billboard`  — billboard marker/label data
  - `kotoba.geo.noise`      — procedural relief noise used by
    `kotoba.geo.mesh/globe-tile-patch`
  - `kotoba.geo.vec3` / `kotoba.geo.math` — small portable vector/scalar
    math helpers shared across the above

  This namespace itself carries no functions — require the sub-namespace
  you need, same as the Rust crate's callers did
  (`kami_geo::projection::...`, `kami_geo::mesh::...`, etc.)."
  (:require [kotoba.geo.billboard]
            [kotoba.geo.constants]
            [kotoba.geo.math]
            [kotoba.geo.mesh]
            [kotoba.geo.noise]
            [kotoba.geo.projection]
            [kotoba.geo.tile]
            [kotoba.geo.vec3]))
