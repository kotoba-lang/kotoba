(ns kotoba.webgpu-rs
  "KAMI webgpu-rs — pure-Clojure port of the CPU-side domain logic in
  `kami-webgpu-rs` (kami-engine, retired per ADR-2607010000). Recovered
  from kami-engine's git history: `git show HEAD:kami-webgpu-rs/src/lib.rs`
  in `orgs/kotoba-lang/kami-engine` for as long as that history exists;
  this repo is the authority going forward.

  `kami-webgpu-rs` was the native (Rust/wgpu) twin of the CLJS
  `kami.webgpu` render executor — both interpreted the *same* EDN
  render-IR (ADR-0001/0040/0044), one driving the browser WebGPU API, the
  other driving wgpu directly, headless (offscreen texture + pixel
  readback) for golden-frame `cargo test` verification. It is NOT
  `kotoba-lang/webgpu` (an unrelated, already-existing foundational
  repo — not touched by this port).

  Sub-namespaces mirror kami-webgpu-rs's own module boundaries:

  - `kotoba.webgpu-rs.render-ir` — EDN render-IR parsing (`Globals`,
    `Instance`, `Light`, `Camera`, `Environment`, `Material`, `Mesh`;
    `parse-ir`/`parse-render-ir`).
  - `kotoba.webgpu-rs.scene`     — `scene.edn` -> render-IR bridge
    (`scene->ir`, the play3d ground+prop-scatter path).
  - `kotoba.webgpu-rs.demo`      — the royale procedural demo scene
    (`demo-city`).
  - `kotoba.webgpu-rs.rng`       — the deterministic xorshift32 PRNG the
    scatter logic shares with the web.
  - `kotoba.webgpu-rs.geometry`  — pure vertex/index mesh generation
    (`cube`, plus `sphere`/`cylinder` ported from kami-webgpu-rs's
    test-only geometry-parity helpers).
  - `kotoba.webgpu-rs.mat4`      — the handful of `glam::Mat4` ops
    kami-webgpu-rs actually used (translation/rotation/scale/perspective/
    look-at/orthographic/transform-point).
  - `kotoba.webgpu-rs.frame`     — per-draw-call pure math (`model-mat`,
    view-projection matrices, uniform/instance buffer packing) extracted
    from `Renderer::draw`.
  - `kotoba.webgpu-rs.config`    — GPU-pipeline configuration as data
    (buffer sizes, shader entry points, formats, vertex-attribute
    layout, light-tuning constants, `align256`).
  - `kotoba.webgpu-rs.edn`       — small EDN-value coercion helpers
    (the narrow subset of kami-scene's tolerant-default reading rules
    kami-webgpu-rs itself called).

  No network, no I/O anywhere in this repo. See README for what
  kami-webgpu-rs had that is intentionally left unported (wgpu device/
  surface/pipeline setup, actual GPU draw calls, shader compilation, the
  window event loop) and why.")

(def unported-summary
  "What kami-webgpu-rs had that stays host-adapter (GPU/window/I-O)
  territory, not ported here — see the README for the full rationale per
  item."
  {:renderer-gpu-resources
   "`Renderer` (device/queue/pipelines/bind-groups/buffers) and its
   `new`/`resize`/`draw`/`device`/`queue` methods — wgpu resource
   creation and the actual `RenderPass`/`draw_indexed` calls."
   :render-async "`render_async`/`render_to_pixels`/`render` — adapter
   requests a GPU adapter/device and drives the headless readback."
   :shaders "`lit_shader.wgsl`/`shadow_shader.wgsl` — WGSL source,
   compiled by wgpu; entry-point names (`vs`/`fs`) are captured as data
   in `kotoba.webgpu-rs.config`, the shader bodies are not reproduced."
   :examples "`examples/live.rs` (winit window/event loop) and
   `examples/render_png.rs` (PNG file I/O) — both 100% host-adapter,
   nothing pure to extract."})
