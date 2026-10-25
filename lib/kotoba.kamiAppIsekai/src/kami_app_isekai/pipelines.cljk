(ns kami-app-isekai.pipelines
  "ISEKAI-local render helper: the breathing-gradient clear-color
  function. Restored from kami-app-isekai's `pipelines.rs`
  (kami-engine/kami-app-isekai, deleted PR #82).

  The original's `BreathingClear` was a native `RenderPipeline` impl
  (wgpu command-encoder recording each frame) that proves prepare/
  record are driven each frame without needing a full scene — this
  namespace ports only the pure time -> RGB color function; the wgpu
  render-pass recording itself is native substrate and NOT ported.

  The bulk of the original file was `pub use kami_pipelines::{...}`
  re-exports (Sky/Terrain adapters, already covered by the already-
  restored `kotoba-lang/pipelines`-family repos where applicable) —
  not ported here since there's no logic to restore for a re-export.")

(defn breathing-clear-color
  "RGB clear color for `tick` (frame counter), a slow breathing gradient
  via three phase-offset sine waves. Matches the original bootstrap/
  debug clear used to prove the render loop drives each frame."
  [tick]
  (let [t (* tick 0.016)
        r (+ (* (+ (* (Math/sin (* t 0.7)) 0.5) 0.5) 0.25) 0.04)
        g (+ (* (+ (* (Math/sin (+ (* t 0.9) 2.1)) 0.5) 0.5) 0.35) 0.05)
        b (+ (* (+ (* (Math/sin (+ (* t 1.1) 4.2)) 0.5) 0.5) 0.45) 0.08)]
    [r g b]))
