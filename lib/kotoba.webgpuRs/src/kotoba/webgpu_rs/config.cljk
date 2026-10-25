(ns kotoba.webgpu-rs.config
  "GPU-pipeline *configuration as data* — extracted from kami-webgpu-rs's
  `Renderer::new`/`draw`/`render_async` constants and `wgpu::*Descriptor`
  literals. This namespace holds no wgpu calls at all: every value here
  was a literal constant or descriptor field in the Rust (buffer sizes,
  shader entry-point names, format enums, vertex-attribute offsets, the
  four light-tuning vec4s written into the uniform buffer). A host adapter
  wiring an actual wgpu (or WebGPU) pipeline reads this data instead of
  re-deriving/duplicating it, so the two backends can't drift on layout.

  No network, no I/O."
  )

;; --- instance cap / buffer sizes -------------------------------------------

(def ^:const max-instances
  "kami-webgpu-rs's `MAX_INST` — the instance buffer is sized for this
  many 96-byte (24-float) instance records regardless of scene size."
  16384)

(def ^:const instance-stride-bytes 96)
(def ^:const instance-stride-floats 24)
(def ^:const cube-vertex-stride-bytes 24)
(def ^:const cube-vertex-stride-floats 6)
(def ^:const uniform-buffer-bytes 240)
(def ^:const uniform-buffer-floats 60)

;; --- shader entry points (both lit_shader.wgsl and shadow_shader.wgsl) ----

(def ^:const vertex-entry-point "vs")
(def ^:const fragment-entry-point "fs")

;; --- formats -----------------------------------------------------------------

(def ^:const color-format
  "The offscreen-render / golden-frame color format `render_async` uses."
  :rgba8-unorm)
(def ^:const depth-format :depth24-plus)
(def ^:const shadow-map-format :depth32-float)
(def ^:const shadow-map-size [2048 2048])
(def ^:const cull-mode :back)
(def ^:const depth-compare-main :less-equal)
(def ^:const depth-compare-shadow :less)
(def ^:const shadow-compare-function :less-equal)

;; --- cube vertex layout (matches kami-webgpu-rs's `cube_attrs`) -----------

(def cube-attributes
  "`[format offset-bytes shader-location]` — the two per-vertex attributes
  (position, normal) read from the cube vertex buffer."
  [{:format :float32x3 :offset 0 :location 0 :name :pos}
   {:format :float32x3 :offset 12 :location 1 :name :normal}])

(def instance-attributes
  "`[format offset-bytes shader-location]` — the six per-instance
  attributes read from the instance buffer: 4 columns of the model
  matrix, then colour+alpha, then metallic/roughness/emissive+pad.
  Matches [[kotoba.webgpu-rs.frame/pack-instance]]'s float layout."
  [{:format :float32x4 :offset 0 :location 2 :name :model-col0}
   {:format :float32x4 :offset 16 :location 3 :name :model-col1}
   {:format :float32x4 :offset 32 :location 4 :name :model-col2}
   {:format :float32x4 :offset 48 :location 5 :name :model-col3}
   {:format :float32x4 :offset 64 :location 6 :name :color}
   {:format :float32x4 :offset 80 :location 7 :name :material}])

;; --- light tuning constants (kami-webgpu-rs's `Renderer::draw` gf[44..60]) -

(def light-a
  "Ambient rgb + sky-mix weight." [0.20 0.22 0.26 0.65])
(def light-b
  "Spec strength lo/hi, rim scale/pow." [0.25 0.9 0.25 3.0])
(def light-c
  "Shininess lo/hi, sun scale, metal factor." [4.0 256.0 0.9 0.7])
(def light-d
  "Gamma, shadow bias factor/min, shadow-map texel (`1/2048`)."
  [2.2 0.0025 0.0006 (/ 1.0 2048.0)])

;; --- misc pure helpers ------------------------------------------------------

(defn align256
  "Round `n` up to the next multiple of 256 — kami-webgpu-rs's `align256`,
  used to compute `bytes_per_row` for a wgpu texture-to-buffer readback
  (rows must be 256-byte aligned)."
  [n]
  (bit-and (+ n 255) (bit-not 255)))
