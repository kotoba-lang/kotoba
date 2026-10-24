(ns engineer-render
  "KAMI Engineering SDK — 2D/3D engineering rendering. Restored from the
  legacy kami-engine/kami-eng-render Rust crate (deleted in kotoba-lang/
  kami-engine PR #82 'Remove Rust workspace from kami-engine') as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Draw commands for schematics, PCB, CAD views, waveforms, FEA color maps —
  built on top of the native kami-render (wgpu) provider. One namespace per
  original Rust concern:
    engineer-render.draw-list  — per-frame draw-command buffer (EDN commands)
    engineer-render.color-map  — FEA post-processing color maps (jet/viridis/...)
    engineer-render.viewport   — pan/zoom + screen<->world transforms

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU. What-to-draw
  is EDN; the wgpu command recorder stays native (ADR-2607010930). Depends on
  kotoba-lang/engineer for shared contracts (constraint/DRC/etc).")
