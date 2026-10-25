(ns kotoba.lang.kami-nv-compat.rtx-renderer
  "Drop-in NVIDIA RTX Renderer API-compat facade — portable .cljc port of
  src/rtx-renderer.ts. Mirrors the documented public shape of the Omniverse
  RTX path-traced renderer (a renderer configured with render settings, fed a
  scene + camera, producing a framebuffer) so existing RTX/Hydra-render host
  code ports to KAMI via require-path-only changes.

  Backed by the clean-room kami-rtx Monte-Carlo path tracer (kami-rt.pathtrace)
  — the R1.2 `kami-rtx-native` path of ADR-2605261800 D10.4 (a from-scratch
  path tracer on kami-rt + WGSL, the fallback to the Mitsuba 3 wgpu upstream
  route D3).

  TS's RtxRenderer class holds only immutable settings (createScene doesn't
  even touch `this`) — no atom/reify needed; `renderer` is a plain
  {:settings ...} map and render/render-sync take it as an explicit first
  arg (create-scene takes no renderer at all, matching the TS method body).
  `render` is `async` in TS (a Promise, for the WebGPU path); on JVM
  kami-rt.index/path-trace already routes WebGPU-or-CPU-fallback
  synchronously, matching the warp.wgpu-backend precedent (\"JVM: sync
  fallback has identical semantics\") — so rtx-render is plain sync here too.

  Clean-room: this re-implements the RTX Renderer *public API shape* (Google
  v. Oracle, 593 U.S. ___ (2021)). No RTX / OptiX / Mitsuba source, headers,
  or SDK binaries are used. The canonical engine has a distinct name —
  `kami-rtx` (see NV_COMPAT_MAP).

  Trademark: NVIDIA® and RTX® are trademarks of NVIDIA Corporation; this
  project is not affiliated with or endorsed by NVIDIA.

  ADR-2605261800 §D1/D6, R1.2 RTX Renderer surface. Wave 39 of
  ADR-2607020130."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.index :as rt]
            [kotoba.lang.kami-nv-compat.kami-rt.pathtrace :as pt]))

;; ── settings ─────────────────────────────────────────────────────────────

(def render-mode-path-traced
  "Unbiased path tracer; the default." :path-traced)
(def render-mode-real-time
  "Same unbiased path tracer, sample/bounce budget clamped for interactivity
  (no separate raster path)." :real-time)

(defn default-render-settings []
  {:mode              render-mode-path-traced
   :samples-per-pixel 64
   :max-bounces       6
   :background        [0 0 0]
   ;; Reserved: AI denoiser toggle. The kami-rtx native denoiser is not yet
   ;; wired, so this is accepted for API parity and currently a no-op.
   :denoise           false})

(defn- ->path-settings
  "REAL_TIME clamps the sample/bounce budget for interactivity."
  [settings]
  (let [rt? (= (:mode settings) render-mode-real-time)]
    {:samples-per-pixel (if rt? (min (:samples-per-pixel settings) 4) (:samples-per-pixel settings))
     :max-bounces       (if rt? (min (:max-bounces settings) 3) (:max-bounces settings))
     :background        (:background settings)}))

;; ── renderer ─────────────────────────────────────────────────────────────

(defn create-renderer
  "RTX-Renderer-shaped {:settings ...} map backed by kami-rtx. `overrides`
  merges over default-render-settings."
  ([] (create-renderer {}))
  ([overrides] {:settings (merge (default-render-settings) overrides)}))

(defn create-scene
  "Build a render scene from triangle meshes + a parallel material list.
  Each entry of `meshes` is a triangle [v0 v1 v2]. Does not depend on any
  renderer instance (matches the TS method body, which never touches
  `this`)."
  [meshes materials]
  (let [scene (pt/build-path-scene meshes materials)]
    {:scene scene :triangle-count (:count (:soup scene))}))

(defn rtx-render
  "Render to a width×height RGBA-float framebuffer. Uses WebGPU when a
  device is available (or one is passed via opts' :device), else the CPU
  path tracer."
  ([renderer scene camera width height] (rtx-render renderer scene camera width height {}))
  ([renderer scene camera width height opts]
   (let [settings (->path-settings (:settings renderer))
         res      (rt/path-trace (:scene scene) camera width height (assoc opts :settings settings))]
     (assoc res :samples-per-pixel (:samples-per-pixel settings)))))

(defn rtx-render-sync
  "Synchronous CPU render (deterministic; useful for tests / headless)."
  [renderer scene camera width height]
  (let [settings (->path-settings (:settings renderer))
        res      (rt/path-trace-cpu (:scene scene) camera width height settings)]
    (assoc res :samples-per-pixel (:samples-per-pixel settings))))

;; ── compat-map metadata ──────────────────────────────────────────────────

(def kami-engine "kami-rtx")
(def adr "ADR-2605261800")
