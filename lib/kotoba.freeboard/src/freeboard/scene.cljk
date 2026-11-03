(ns freeboard.scene
  "Board → kami ECS scene (entities + camera + assets) for kami-engine-sdk-clj.
   Each board item becomes a renderable entity carrying the exact component
   attrs kami.render queries (`:kami/eid` `:transform/translation`
   `:transform/scale` `:mesh/asset` `:material/asset` `:material/tint`); per-item
   fill → per-instance tint (v2 packing). The viewport (pan/zoom) is baked into
   screen-space transforms (2D). Host adapters feed these to kami.ecs/world →
   kami.render/frame → kami.gpu/submit!. See ADR-2606280200."
  (:require [freeboard.board :as b]
            [freeboard.render :as r]))

(def nintendo-cream r/nintendo-cream)

(defn hex->rgba
  "\"#rrggbb\" → [r g b 1.0] floats (nil/invalid → white)."
  [hex]
  (if (and (string? hex) (= 7 (count hex)) (= \# (first hex)))
    (let [p (fn [i] (/ (#?(:clj Integer/parseInt :cljs js/parseInt) (subs hex i (+ i 2)) 16) 255.0))]
      [(p 1) (p 3) (p 5) 1.0])
    [1.0 1.0 1.0 1.0]))

(def kind-tint
  {:sticky [1.0 0.92 0.54 1.0] :frame [0.97 0.95 0.86 1.0] :text [1.0 1.0 1.0 1.0]
   :shape  [0.80 0.85 1.0 1.0] :image [0.90 0.90 0.90 1.0]
   :connector [0.5 0.5 0.5 1.0] :ink [0.13 0.13 0.13 1.0]})

;; ---- flat 2D shader (clj-authored WGSL, registered via register_shader) -----
;; kami-render's default pipeline applies 3D diffuse lighting which mutes flat
;; board colours. A board is 2D, so we register a *flat* pipeline (albedo·tint,
;; no lighting) and tag every entity with :shader/asset → bright, exact colours.
;; This is the data-driven shader path (ARCHITECTURE Model A): no wasm rebuild.
;; The VsIn/bind-group layout must match host.rs build_pipeline (loc 0-7, group0
;; camera, group1 material) and use entry points vs_main/fs_main.
(def flat-shader-wgsl
  "struct Camera { view_proj: mat4x4<f32> };
@group(0) @binding(0) var<uniform> camera: Camera;
struct Material { albedo: vec4<f32> };
@group(1) @binding(0) var<uniform> material: Material;
struct VsIn { @location(0) pos: vec3<f32>, @location(1) normal: vec3<f32>, @location(2) uv: vec2<f32>,
              @location(3) m0: vec4<f32>, @location(4) m1: vec4<f32>, @location(5) m2: vec4<f32>, @location(6) m3: vec4<f32>,
              @location(7) tint: vec4<f32> };
struct VsOut { @builtin(position) clip: vec4<f32>, @location(0) tint: vec4<f32> };
@vertex fn vs_main(in: VsIn) -> VsOut {
  let model = mat4x4<f32>(in.m0, in.m1, in.m2, in.m3);
  var out: VsOut;
  out.clip = camera.view_proj * model * vec4<f32>(in.pos, 1.0);
  out.tint = in.tint;
  return out;
}
@fragment fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
  return material.albedo * in.tint;
}")

(def flat-shader {:asset/id "freeboard:flat2d" :asset/kind :shader
                  :asset/data {:wgsl flat-shader-wgsl :layout ""}})

(defn- draw->entity [d]
  (let [[sx sy sw sh] (:rect d)
        text (when (= :text (:kind d)) (apply str (map :text (:text/runs d))))]
    (if (seq text)
      ;; text → a glyph-quad mesh ("text:<eid>", registered via register-text!)
      ;; sampling the host SDF atlas; entity places the text block (pixel-space
      ;; mesh, so scale 1). Dark ink unless an explicit fill is given.
      {:kami/eid              (:eid d)
       :transform/translation [sx sy (* 0.001 (:z d))]
       :transform/scale       [1.0 1.0 1.0]
       :mesh/asset            (str "text:" (:eid d))
       :material/asset        "freeboard:flat"
       :texture/asset         "kami:glyph-atlas"
       :material/params       {:tint (if (:fill d) (hex->rgba (:fill d)) [0.12 0.12 0.12 1.0])}}
    (cond-> {:kami/eid               (:eid d)
             :transform/translation  [sx sy (* 0.001 (:z d))]  ; small z for stable layering
             :transform/scale        [(max 1.0 sw) (max 1.0 sh) 1.0]
             :mesh/asset             "freeboard:quad"
             :material/asset         "freeboard:flat"
             :shader/asset           "freeboard:flat2d"        ; flat (unlit) pipeline
             ;; kami.render/merge-instances reads per-instance tint from
             ;; [:material/params :tint] (NOT :material/tint) — match that or it
             ;; defaults to white (found via freeboard.debug).
             :material/params        {:tint (if (:fill d) (hex->rgba (:fill d))
                                                (kind-tint (:kind d) [1.0 1.0 1.0 1.0]))}}
      ;; image items sample a registered texture — host selects the textured
      ;; pipeline when :texture/asset is present; tint white = unmodulated image.
      (:image/texture d) (assoc :texture/asset (:image/texture d)
                                :material/params {:tint [1.0 1.0 1.0 1.0]})))))

;; ---- lines as quads (no separate line pipeline needed) --------------------
(defn- sincos [a] #?(:clj [(Math/sin a) (Math/cos a)] :cljs [(js/Math.sin a) (js/Math.cos a)]))
(defn- atan2 [y x] #?(:clj (Math/atan2 y x) :cljs (js/Math.atan2 y x)))
(defn- hypot [x y] #?(:clj (Math/hypot x y) :cljs (js/Math.hypot x y)))

(defn seg->entity
  "A screen-space segment [[x1 y1][x2 y2]] of width `w` → a rotated thin quad
   entity (corner-origin unit quad, scale [L w 1], z-rotation θ, translated so
   the quad is centred on the segment)."
  [eid [[x1 y1] [x2 y2]] w z tint]
  (let [dx (- x2 x1) dy (- y2 y1)
        L  (max 1.0 (hypot dx dy))
        th (atan2 dy dx)
        [s c] (sincos th)
        mx (/ (+ x1 x2) 2.0) my (/ (+ y1 y2) 2.0)
        ;; translation = midpoint - R(θ)·[L/2, w/2]
        ox (- mx (- (* c (/ L 2.0)) (* s (/ w 2.0))))
        oy (- my (+ (* s (/ L 2.0)) (* c (/ w 2.0))))]
    {:kami/eid              eid
     :transform/translation [ox oy (* 0.001 z)]
     :transform/rotation    [0.0 0.0 (#?(:clj Math/sin :cljs js/Math.sin) (/ th 2.0))
                             (#?(:clj Math/cos :cljs js/Math.cos) (/ th 2.0))]
     :transform/scale       [L (max 1.0 w) 1.0]
     :mesh/asset            "freeboard:quad"
     :material/asset        "freeboard:flat"
     :shader/asset          "freeboard:flat2d"
     :material/params       {:tint tint}}))

(defn- line-entities [d]
  (let [tint (if (:stroke d) (hex->rgba (:stroke d)) (:connector kind-tint))
        z    (:z d)]
    (case (:kind d)
      :connector (let [pts (:connector/polyline d)]            ; bézier-sampled S-curve
                   (map-indexed (fn [i seg] (seg->entity (str (:eid d) ":" i) seg 2.0 z tint))
                                (partition 2 1 pts)))
      :ink       (let [pts (:ink/polyline d) w (:ink/width d 2.0)]
                   (map-indexed (fn [i seg] (seg->entity (str (:eid d) ":" i) seg w z tint))
                                (partition 2 1 pts)))
      nil)))

(defn board->entities
  "Renderable quad entities. Rect items → one quad; connectors (bézier curves)
   and ink → thin quad segments (same quad+tint pipeline, no line pipeline)."
  [board]
  (let [draws (:draws (r/draw-list board))]
    (into (mapv draw->entity (remove #(#{:connector :ink} (:kind %)) draws))
          (mapcat line-entities (filter #(#{:connector :ink} (:kind %)) draws)))))

(defn camera-entity
  "Active **orthographic** screen-space camera (kami.render ortho support added
   in kami-engine-sdk-clj): pixel (0,0) top-left, y down — so the baked
   screen-space item quads are pixel-correct. `[w h]` = canvas pixel size."
  [[w h]]
  {:kami/eid :freeboard/camera :camera/active? true
   :camera/projection :ortho :camera/ortho-w (double w) :camera/ortho-h (double h)
   :camera/near -1.0 :camera/far 1.0
   :transform/translation [0.0 0.0 0.0]})

(def quad-mesh
  ;; unit quad [0,0]→[1,1]. kami-render's default pipeline expects each vertex
  ;; INTERLEAVED as pos3 + norm3 + uv2 (VERTEX_STRIDE = 32 B, host.rs vbuf
  ;; locations 0/1/2). A pos-only mesh is mis-strided → degenerate geometry →
  ;; nothing visible (the "items don't render" bug found via freeboard.debug).
  ;; Vertices/indices live under :asset/data (the shape ensure-assets! reads).
  {:asset/id "freeboard:quad" :asset/kind :mesh
   :asset/data {:vertices [0.0 0.0 0.0  0.0 0.0 1.0  0.0 0.0    ; pos, normal +Z, uv
                           1.0 0.0 0.0  0.0 0.0 1.0  1.0 0.0
                           1.0 1.0 0.0  0.0 0.0 1.0  1.0 1.0
                           0.0 1.0 0.0  0.0 0.0 1.0  0.0 1.0]
                ;; CW winding: the ortho proj flips Y, which inverts triangle
                ;; winding in NDC. kami-render culls back faces (front_face Ccw),
                ;; so a naive CCW quad is culled → invisible. Reverse to stay
                ;; front-facing after the flip (found via freeboard.debug).
                :indices  [0 2 1  0 3 2]}})

(def flat-material {:asset/id "freeboard:flat" :asset/kind :material :asset/data {:params []}})

(defn scene-snapshot
  "{:snapshot/assets [...] :snapshot/entities [...]} — assets via
   kami.gpu/ensure-assets!, entities via kami.ecs/load-snapshot. `screen` is the
   canvas pixel size [w h] for the ortho camera."
  ([board] (scene-snapshot board [1280 720]))
  ([board screen]
   {:snapshot/assets   [quad-mesh flat-material flat-shader]
    :snapshot/entities (conj (board->entities board) (camera-entity screen))}))
