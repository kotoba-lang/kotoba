(ns kami-app-isekai
  "KAMI App Isekai — the ISEKAI reference-implementation game entry
  (per-game topology on top of the `kami-app` Builder SDK). Restored
  from the legacy kami-engine/kami-app-isekai Rust crate (2107 lines
  across `lib.rs`/`omniverse.rs`/`pipelines.rs`, deleted in
  kotoba-lang/kami-engine PR #82 'Remove Rust workspace from
  kami-engine') as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  The original crate was primarily a `wasm-bindgen` entrypoint
  (`run_isekai_v2`/`run_isekai_v2_scene`) orchestrating `KamiApp`
  builder calls, a per-frame `on_update` tick closure driving DEC
  field simulation (`kami_dec::ScalarField`/`EdgeField`/`FaceField` —
  heat/moisture/wind/EM fields tightly coupled to native `Rc<RefCell<
  ...>>` state and `kami_pipelines` GPU adapters), voxel-chunk
  streaming, and an Omniverse/PhysX/USD facade — native WASM/wgpu
  substrate with no meaningful portable representation as a whole
  program. Rather than attempt a 1:1 tick-loop port (which would carry
  no computational value without the native simulation state it
  operates on), this restoration extracts the genuinely PORTABLE
  computational kernels and configuration data:

    kami-app-isekai.voxel-world — 2-octave value noise, voxel palette,
      terrain-height generation rule, and the pre-authored demo-house
      voxel layout (pure functions/data; the original mutated a native
      VoxelChunkAdapter as a side effect of the same computation)
    kami-app-isekai.pipelines   — the breathing-gradient clear-color
      function (pure time -> RGB; the wgpu render-pass recording
      itself is native)
    kami-app-isekai.omniverse   — the default USDA scene-description
      text constant (pure data; USD parsing/PhysX orchestration is
      native)

  Excluded entirely (native-only, no portable logic): the wasm-bindgen
  entrypoints, the per-frame DEC tick closure and its native Rc<RefCell>
  field state, voxel-chunk GPU streaming/upload, and the Omniverse/USD/
  PhysX parse-and-drive orchestration.

  kami-app-isekai.heightmap-color is NOT a restoration from the original
  crate (there was no top-down heightmap view there) — it's a small pure
  height -> RGB gradient + grid sampler added to give voxel-world's
  terrain-height kernel its first real, pixel-verified visualization (see
  test/render_pixel_test.clj, which draws it through kotoba-lang/webgpu's
  kami.sprite-gpu as a test/demo-only sibling dependency).

  Zero-dep portable CLJC."
  (:require [kami-app-isekai.voxel-world]
            [kami-app-isekai.pipelines]
            [kami-app-isekai.omniverse]
            [kami-app-isekai.heightmap-color]))
