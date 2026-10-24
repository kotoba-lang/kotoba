(ns terrain
  "kami-terrain: Decima-style heightmap terrain engine.

  Restored from kotoba-lang/kami-engine's kami-terrain crate (deleted in PR #82
  \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root). Zero-dep portable CLJC: procedural
  generation (value noise + FBM), splatmap material blending, chunk-based mesh
  generation, and Gerstner-wave water surfaces for open-world rendering.
  Design reference: Guerrilla Games Decima Engine (Horizon Zero Dawn).

  This namespace re-exports the public surface of the sibling terrain.*
  namespaces (mirroring the original lib.rs `pub use` list) so callers can
  `(require '[terrain :as terrain])` alone for common operations."
  (:require [terrain.heightmap :as heightmap]
            [terrain.chunk :as chunk]
            [terrain.noise :as noise]
            [terrain.splatmap :as splatmap]
            [terrain.water :as water]
            [terrain.biome :as biome]))

;; heightmap
(def default-heightmap-config heightmap/default-config)
(def generate-heightmap heightmap/generate)
(def sample-heightmap heightmap/sample)
(def heightmap-normal heightmap/normal)

;; chunk
(def generate-chunk-mesh chunk/generate-chunk-mesh)

;; noise
(def fbm-noise noise/fbm-noise)
(def value-noise noise/value-noise)

;; splatmap
(def splatmap-from-heightmap splatmap/from-heightmap)

;; water
(def default-water-config water/default-config)
(def default-waves water/default-waves)
(def waves-from-wind water/waves-from-wind)
(def generate-water-mesh water/generate-water-mesh)

;; biome
(def biome-values biome/biome-values)
(def biome-heightmap-config biome/heightmap-config)
(def biome-splat-thresholds biome/splat-thresholds)
(def biome-palette biome/palette)
(def biome-name biome/biome-name)
