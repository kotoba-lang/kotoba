(ns kotoba.web-modelb
  "Pure-Clojure port of the portable parts of `kotoba-lang/kami-engine`'s
  `kami-web-modelb` Rust crate (ADR-2607010930, clj-wgsl migration Phase 4).

  `kami-web-modelb` (\"Web Model-B: the VRM dance running in-browser as a
  compiled-CLJ game\") is a GPU bridge, not a logic crate: it composes a
  native `kami-live` LiveShow with a wasmi-compiled `dance/logic.clj`,
  ticks both per frame, rasterises the resulting render-IR on the CPU
  (`kami-webgpu-rs::render` — reusing the SAME `{:globals :instances}`
  render-IR shape `kotoba-lang/kami-web`'s `kotoba.web.render-ir` ports),
  and blits the pixels to a `<canvas>` via a minimal `wgpu` fullscreen-quad
  pipeline. Almost none of that is portable: the compiled-CLJ execution
  runs *inside* `kami-script-runtime`'s wasmi WASM-in-WASM sandbox (a
  Rust-only capability), and the GPU blit is pure `wgpu` adapter glue.

  What *is* portable, and lives here:

  - [[kotoba.web-modelb.config]] — the fixed dance-viewer camera preset,
    the headless-verification canvas size, the shipped-asset path
    references, and the `dt` (seconds) -> `dt_ms` (integer milliseconds)
    frame-timing conversion `WebDance::tick` performs.

  See that namespace's docstring for exactly what was left unported and
  why."
  (:require [kotoba.web-modelb.config]))

(def port-manifest
  "What was ported vs. left adapter-only, as data (for tooling/audits)."
  {:source-repo "kotoba-lang/kami-engine"
   :source-crate "kami-web-modelb"
   :adr "2607010930"
   :ported [{:ns "kotoba.web-modelb.config" :from "kami-web-modelb/src/lib.rs, kami-web-modelb/examples/render_png.rs"}]
   :adapter-only ["kami-web-modelb/src/gpu.rs (wgpu surface + fullscreen-quad blit pipeline + WGSL shader)"
                  "kami-web-modelb/src/lib.rs (WebDanceGpu/WebDance: kami_script_runtime wasmi WASM-in-WASM execution, hecs::World, kami_live::scene::DanceScene ticking)"
                  "kami-web-modelb/examples/render_png.rs (host-only headless PNG verification tool)"]
   :shared-schema {:namespace "kotoba.web.render-ir"
                    :repo "kotoba-lang/kami-web"
                    :note "WebDance::tick returns the same {:globals :instances} render-IR EDN shape kami-web's render_ir entry consumes — see that repo's kotoba.web.render-ir namespace for the schema/camera-math port."}})
