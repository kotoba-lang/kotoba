(ns vegetation
  "KAMI Vegetation: Decima-style procedural vegetation.

  Restored from the deleted `kami-vegetation` Rust crate
  (kotoba-lang/kami-engine, deleted in PR #82 \"Remove Rust workspace from
  kami-engine\") as zero-dependency portable CLJC, per ADR-2607010930 (the
  clj-wgsl migration, com-junkawasaki/root).

  Poisson-disk placement + biome rules (height + slope + splatmap) +
  taxonomy-driven procedural mesh generation + distance-based LOD/culling
  for GPU instancing. Pure data + pure functions throughout — no IO, no
  GPU dispatch. Modules mirror the original `pub mod` declarations 1:1:

    vegetation.taxonomy  — botanical classification -> generation profile
    vegetation.species   — species placement rules + render params
    vegetation.instance   — per-plant GPU instance data
    vegetation.lod        — distance-based LOD tier classification
    vegetation.cull       — distance culling + spatial patch clustering
    vegetation.mesh       — taxonomy-profile-driven procedural mesh generation
    vegetation.placement  — Poisson-disk scatter placement over terrain"
  (:require [vegetation.species :as species]
            [vegetation.placement :as placement]
            [vegetation.instance :as instance]
            [vegetation.lod :as lod]
            [vegetation.cull :as cull]
            [vegetation.mesh :as mesh]
            [vegetation.taxonomy :as taxonomy]))

;; Re-exports mirroring the original `kami_vegetation::lib.rs` `pub use`.
(def species-table species/species-table)
(def default-placement-config placement/default-placement-config)
(def place-instances placement/place-instances)
(def classify-lod lod/classify-lod)
(def cull-by-distance cull/cull-by-distance)
(def cull-to-buffer cull/cull-to-buffer)
(def mesh-from-profile mesh/mesh-from-profile)
(def default-catalog taxonomy/default-catalog)
