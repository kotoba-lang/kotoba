(ns kotoba.web.render-ir
  "The generic EDN render-IR SHAPE (ADR-0002, network-isekai), ported from
  `kami-web/src/entries/render_ir.rs` — `run_with_render_ir` is documented
  as *the* single data-driven renderer entry for new games (ADR-0039); this
  namespace is the CLJ-side authority for that shape plus the pure geometry
  math around it (default camera derivation, per-instance model matrix,
  unit-cube mesh data).

  Render-IR shape:

    {:globals {:sky {:horizon [r g b] :sun-dir [x y z] :sun [r g b]}
               :eye    [x y z]     ; optional — explicit camera
               :target [x y z]}    ; optional — explicit camera
     :instances [{:pos [x y z] :color [r g b] :size [w h] :yaw radians} ...]}

  Left unported (adapter-only, stays in Rust): everything from `ensure_init`
  down — wgpu device/surface/pipeline/buffer setup, the persistent
  instance-buffer upload, and the WGSL shader (`SHADER` — reproduced here
  only in a comment for reference, never executed from cljc). Also
  unported: `run_with_render_ir` / `render_ir_init` / `render_ir_draw`
  themselves (the stateful, thread-local WASM entry points) — this
  namespace only covers what those functions *compute*, not the GPU work
  they *do*."
  (:require [kotoba.web.math :as math]))

;; ---------------------------------------------------------------------
;; Schema (plain predicates, no clojure.spec dep — matches kami-scene-contracts style)
;; ---------------------------------------------------------------------

(defn vec3? [v] (and (vector? v) (= 3 (count v)) (every? number? v)))
(defn vec2? [v] (and (vector? v) (= 2 (count v)) (every? number? v)))

(defn sky? [sky]
  (and (map? sky)
       (vec3? (:horizon sky))
       (vec3? (:sun-dir sky))
       (vec3? (:sun sky))))

(defn globals? [g]
  (and (map? g)
       (sky? (:sky g))
       (or (nil? (:eye g)) (vec3? (:eye g)))
       (or (nil? (:target g)) (vec3? (:target g)))))

(defn render-instance? [inst]
  (and (map? inst)
       (vec3? (:pos inst))
       (vec3? (:color inst))
       (or (nil? (:size inst)) (vec2? (:size inst)))
       (or (nil? (:yaw inst)) (number? (:yaw inst)))))

(defn render-ir?
  "True if `ir` matches the `{:globals :instances}` render-IR shape."
  [ir]
  (and (map? ir)
       (globals? (:globals ir))
       (vector? (:instances ir))
       (every? render-instance? (:instances ir))))

;; ---------------------------------------------------------------------
;; Defaults (mirrors the `arr3`/`fnum` fallback values in render_ir.rs::draw)
;; ---------------------------------------------------------------------

(def default-size [1.0 1.0])
(def default-yaw 0.0)

(defn instance-size [inst] (or (:size inst) default-size))
(defn instance-yaw [inst] (or (:yaw inst) default-yaw))

;; ---------------------------------------------------------------------
;; Per-instance model matrix — Translate(pos + [0,h/2,0]) * RotY(yaw) * Scale(w,h,w)
;; ---------------------------------------------------------------------

(defn instance-model-matrix
  "16-element column-major model matrix for one render-IR instance, matching
  `render_ir.rs::draw`'s `Mat4::from_translation(...) * Mat4::from_rotation_y(...) *
  Mat4::from_scale(...)`."
  [inst]
  (let [[px py pz] (:pos inst)
        [bw bh] (instance-size inst)
        yaw (instance-yaw inst)
        t (math/mat4-translation [px (+ py (* bh 0.5)) pz])
        r (math/mat4-rotation-y yaw)
        s (math/mat4-scale [bw bh bw])]
    (math/mat4-mul (math/mat4-mul t r) s)))

;; ---------------------------------------------------------------------
;; Centroid + default camera (overview of centroid when :eye/:target absent)
;; ---------------------------------------------------------------------

(defn centroid
  "Average `:pos` of all instances, or `[0 0 0]` for an empty render-IR."
  [instances]
  (if (empty? instances)
    [0.0 0.0 0.0]
    (let [n (count instances)
          [sx sy sz] (reduce (fn [[ax ay az] {[x y z] :pos}] [(+ ax x) (+ ay y) (+ az z)])
                              [0.0 0.0 0.0] instances)]
      [(/ sx n) (/ sy n) (/ sz n)])))

(defn default-camera
  "`(eye, target)` pair — explicit `globals :eye/:target` if present, else an
  overview of the instance centroid offset by `[+60 +80 +60]`, matching
  `render_ir.rs::draw`'s fallback."
  [globals instances]
  (if (:eye globals)
    [(:eye globals) (:target globals)]
    (let [[cx _cy cz] (centroid instances)]
      [[(+ cx 60.0) 80.0 (+ cz 60.0)] [cx 0.0 cz]])))

;; ---------------------------------------------------------------------
;; view-proj for a render-IR frame — fov 60deg, near 0.5, far 4000 (render_ir.rs::draw)
;; ---------------------------------------------------------------------

(def default-fov-y (/ Math/PI 3.0)) ; 60 degrees in radians
(def default-near 0.5)
(def default-far 4000.0)

(defn frame-view-proj
  "16-element column-major view-projection matrix for one render-IR frame at
  viewport `width`x`height`, matching `render_ir.rs::draw`'s camera setup
  (`60deg` fov, aspect clamped to a `0.1` floor, near `0.5`/far `4000`)."
  [ir width height]
  (let [[eye target] (default-camera (:globals ir) (:instances ir))
        aspect (max 0.1 (/ (double width) (max 1.0 (double height))))]
    (apply math/view-projection (concat eye target [default-fov-y aspect default-near default-far]))))

;; ---------------------------------------------------------------------
;; Unit cube mesh (24 verts / 36 indices) — direct port of render_ir.rs::cube()
;; ---------------------------------------------------------------------

(def ^:private cube-faces
  "`[normal [4 corner positions]]` per face, in the exact order/winding of
  `render_ir.rs::cube()` (+Z, -Z, +X, -X, +Y, -Y)."
  [[[0.0 0.0 1.0] [[-0.5 -0.5 0.5] [0.5 -0.5 0.5] [0.5 0.5 0.5] [-0.5 0.5 0.5]]]
   [[0.0 0.0 -1.0] [[0.5 -0.5 -0.5] [-0.5 -0.5 -0.5] [-0.5 0.5 -0.5] [0.5 0.5 -0.5]]]
   [[1.0 0.0 0.0] [[0.5 -0.5 0.5] [0.5 -0.5 -0.5] [0.5 0.5 -0.5] [0.5 0.5 0.5]]]
   [[-1.0 0.0 0.0] [[-0.5 -0.5 -0.5] [-0.5 -0.5 0.5] [-0.5 0.5 0.5] [-0.5 0.5 -0.5]]]
   [[0.0 1.0 0.0] [[-0.5 0.5 0.5] [0.5 0.5 0.5] [0.5 0.5 -0.5] [-0.5 0.5 -0.5]]]
   [[0.0 -1.0 0.0] [[-0.5 -0.5 -0.5] [0.5 -0.5 -0.5] [0.5 -0.5 0.5] [-0.5 -0.5 0.5]]]])

(defn cube
  "`{:vertices [{:pos [x y z] :normal [x y z]} ...] :indices [u16 ...]}` —
  24 vertices (4 per face x 6 faces) + 36 indices (2 triangles per face,
  `[b b+1 b+2 b b+2 b+3]`), matching `render_ir.rs::cube()` exactly."
  []
  (loop [faces cube-faces verts [] indices []]
    (if (empty? faces)
      {:vertices verts :indices indices}
      (let [[normal quad] (first faces)
            b (count verts)
            new-verts (mapv (fn [p] {:pos p :normal normal}) quad)
            new-indices [b (+ b 1) (+ b 2) b (+ b 2) (+ b 3)]]
        (recur (rest faces) (into verts new-verts) (into indices new-indices))))))

;; ---------------------------------------------------------------------
;; Reference only — never executed from cljc (documents the GPU adapter boundary)
;; ---------------------------------------------------------------------

(def shader-wgsl-reference
  "Verbatim copy of `render_ir.rs`'s `SHADER` constant, kept here only as a
  cross-reference for anyone porting the actual draw call later; this
  string is inert data in cljc — no WGSL/WASM execution happens here."
  "struct G { view_proj: mat4x4<f32>, sun_dir: vec4<f32>, sun_col: vec4<f32>, sky: vec4<f32> };
@group(0) @binding(0) var<uniform> g: G;
struct VO { @builtin(position) clip: vec4<f32>, @location(0) n: vec3<f32>, @location(1) col: vec3<f32> };
@vertex
fn vs(@location(0) pos: vec3<f32>, @location(1) normal: vec3<f32>,
      @location(2) m0: vec4<f32>, @location(3) m1: vec4<f32>, @location(4) m2: vec4<f32>, @location(5) m3: vec4<f32>,
      @location(6) color: vec4<f32>) -> VO {
  let model = mat4x4<f32>(m0, m1, m2, m3);
  var o: VO;
  o.clip = g.view_proj * model * vec4<f32>(pos, 1.0);
  o.n = normalize((model * vec4<f32>(normal, 0.0)).xyz);
  o.col = color.rgb;
  return o;
}
@fragment
fn fs(i: VO) -> @location(0) vec4<f32> {
  let L = normalize(-g.sun_dir.xyz);
  let lambert = max(dot(normalize(i.n), L), 0.0);
  let amb = mix(vec3<f32>(0.18, 0.2, 0.26), g.sky.rgb * 0.5, normalize(i.n).y * 0.5 + 0.5);
  return vec4<f32>(i.col * (amb + lambert * g.sun_col.rgb * 0.85), 1.0);
}")
