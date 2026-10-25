(ns kami-app-quarry-walk
  "KAMI App Quarry Walk — the second reference game validating the
  `kami-app` Builder + `kami-pipelines` topology for multi-game reuse.
  Restored from the legacy kami-engine/kami-app-quarry-walk Rust crate
  (76 lines, deleted in kotoba-lang/kami-engine PR #82 'Remove Rust
  workspace from kami-engine') as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  The original crate was almost entirely a `wasm-bindgen` entrypoint
  (`run_quarry_walk_v2`) orchestrating `KamiApp`/`kami_pipelines`/
  `kami_terrain_scene` builder calls — native WASM/wgpu substrate with
  no portable logic of its own ('No pipeline code here: game logic =
  biome selection + spawn + camera/input wiring. All rendering reuses
  kami_pipelines.', per its own doc comment). What IS portable is the
  game's CONFIGURATION: spawn position, camera mode, terrain/water
  adapter parameters. This namespace captures that configuration as
  plain CLJC data — a specification a native/WASM host could read to
  reconstruct the original scene setup, rather than a re-implementation
  of the builder orchestration itself.

  Zero-dep portable CLJC.")

(def biome
  "The terrain biome this game uses (resolved from kami-terrain-scene's
  biomes.edn at runtime; falls back to the compiled-in BiomePreset if
  unavailable)."
  "quarry")

(def spawn-position
  "Quarry biome peaks ~120m. Spawn 140m up on the central ridge so the
  player looks down over the formation. `[x y z]`."
  [0.0 140.0 120.0])

(def camera-config
  {:mode :first-person :spawn spawn-position :yaw 0.0 :pitch -0.4})

(def input-mode :wasd-fps)

(def terrain-config
  "Passed to TerrainAdapter/streaming[-with-config]: sea-level 77.0
  (quarry biome sand_line=5 keeps water in valleys), chunk-size 128,
  lod-levels 2."
  {:sea-level 77.0 :chunk-size 128 :lod-levels 2})

(def water-config
  {:size 1024.0 :sea-level 4.0})

(def app-config
  {:label "quarry-walk" :hud-publish? true
   :camera camera-config :input-mode input-mode
   :pipelines [:sky :terrain :water]
   :biome biome :terrain terrain-config :water water-config})
