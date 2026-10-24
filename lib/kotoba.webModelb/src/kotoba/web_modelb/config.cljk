(ns kotoba.web-modelb.config
  "Pure config + frame-timing math ported from `kami-web-modelb/src/lib.rs`
  and `kami-web-modelb/examples/render_png.rs`.

  `kami-web-modelb` (\"Model B — brain-on-host\") is a thin GPU bridge: it
  composes a native `kami-live::scene::DanceScene` (LiveShow choreography)
  with a **compiled-CLJ** `dance/logic.clj` driven wasm-in-wasm by
  `kami-script-runtime`'s wasmi backend, ticks both, and rasterises the
  resulting render-IR (see `kotoba-lang/kami-web`'s
  `kotoba.web.render-ir` for that same `{:globals :instances}` shape) via
  `kami-webgpu-rs::render` blitted to a `<canvas>` through `wgpu`.

  Almost the entire crate is host-adapter orchestration of *other* Rust
  crates that have no Clojure port to bridge to (`kami_script_runtime`'s
  wasmi WASM-in-WASM execution, `hecs::World`, `kami_webgpu_rs`'s CPU
  rasteriser, `wgpu` surface/texture/blit-pipeline setup) — none of that
  is meaningfully portable. What *is* pure, and lives here: the fixed
  dance-viewer camera preset and the `dt` (seconds) -> `dt_ms` (integer
  milliseconds) conversion `WebDance::tick` performs before driving the
  compiled-CLJ systems.

  Left unported (adapter-only, stays in Rust): `gpu.rs` in its entirety
  (wgpu surface + fullscreen-quad blit pipeline + WGSL shader),
  `WebDanceGpu`/`WebDance` (wasm-bindgen structs wrapping
  `kami_live::scene::DanceScene` + `KamiScriptRuntime` + `hecs::World`),
  and `examples/render_png.rs` (headless PNG dump of the exact GPU-path
  pixels — a host-only verification tool, not portable logic)."
  )

;; ---------------------------------------------------------------------
;; Dance-viewer camera preset (WebDanceGpu::frame / examples/render_png.rs)
;; ---------------------------------------------------------------------

(def dance-camera
  "The fixed eye/target `WebDanceGpu::frame` and `examples/render_png.rs`
  both set on the parsed render-IR globals before rasterising —
  `g.eye = Some([0.0, 1.5, 4.2]); g.target = Some([0.0, 0.95, 0.0]);`"
  {:eye [0.0 1.5 4.2]
   :target [0.0 0.95 0.0]})

(def render-png-canvas
  "The `(w, h)` used by `examples/render_png.rs`'s headless verification
  render — `let (w, h) = (420u32, 480u32);`."
  {:width 420 :height 480})

;; ---------------------------------------------------------------------
;; scene/logic asset paths (include_str! in lib.rs / render_png.rs)
;; ---------------------------------------------------------------------

(def dance-assets
  "The shipped dance artifacts `WebDance::new` / `render_png.rs` embed via
  `include_str!` — choreography as data (`scene.edn`), behaviour as
  compiled Clojure (`logic.clj`). Paths are relative to the Rust crate
  root, kept here only as a data cross-reference."
  {:scene "../kami-clj-play3d/games/dance/scene.edn"
   :logic "../kami-clj-play3d/games/dance/logic.clj"})

;; ---------------------------------------------------------------------
;; frame-timing: dt (seconds, f32) -> dt_ms (integer milliseconds)
;; ---------------------------------------------------------------------

(defn dt->ms
  "`WebDance::tick`'s `let dt_ms = (dt * 1000.0).max(0.0) as i64;` — the
  duration (seconds) passed to `call_systems`/`integrate`, floored to a
  non-negative integer millisecond count (matches Rust's `as i64` cast,
  which truncates toward zero after the `max(0.0)` floor)."
  [dt]
  (long (max 0.0 (* (double dt) 1000.0))))
