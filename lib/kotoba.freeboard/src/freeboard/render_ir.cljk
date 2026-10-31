(ns freeboard.render-ir
  "freeboard board → the **canonical kami EDN render-IR** (ADR-0044,
   `kami-engine/kami-webgpu-rs` + `kami-web::run_with_render_ir`): the single
   `{:globals :camera :instances …}` data surface that native (wgpu) and web
   (CLJS/WebGPU) both interpret, and that kami-live emits. This is the *interop*
   form — freeboard's pixel-exact 2D renderer keeps the Model-A path
   (`freeboard.scene` → `kami.render/frame` → `kami.ipc`), but every board can
   ALSO be expressed in the shared render-IR so it composes with the rest of the
   engine (games, dance scenes, mangaka renders). Pure data; see ADR-2606280200.

   ADR-0044 v1 instance: {:pos [x y z] :color [r g b] :size [w h] :yaw θ
                          :metallic :roughness :emissive}. v2 adds
   :camera/:env/:lights/:materials/:meshes/:animations/:post (all optional)."
  (:require [freeboard.board :as b]
            [freeboard.scene :as sc]))

(defn- rgb [hex] (vec (take 3 (sc/hex->rgba hex))))

(defn- item->instance
  "A rect item → one billboard instance (centre, RGB, screen size, yaw)."
  [it]
  (let [[cx cy] (b/item-center it)]
    {:pos   [(double cx) (double cy) (* 0.001 (double (:item/z it 0)))]
     :color (rgb (or (:item/fill it) "#cccccc"))
     :size  [(double (:item/w it)) (double (:item/h it))]
     :yaw   (double (:item/rotation it 0.0))
     :metallic 0.0 :roughness 1.0 :emissive 0.0}))

(defn- line->instances
  "Connector (bézier) / ink → thin billboard instances per segment, matching the
   2D renderer's quad-tessellation (so the render-IR draws the same strokes)."
  [board it]
  (let [pts (case (:item/kind it)
              :ink       (:ink/points it)
              :connector (b/connector-endpoints board it)
              nil)
        col (rgb (or (:item/stroke it) "#333333"))
        w   (:ink/width it 2.0)]
    (when (and pts (>= (count pts) 2))
      (for [[[x1 y1] [x2 y2]] (partition 2 1 pts)
            :let [dx (- x2 x1) dy (- y2 y1)
                  len (max 1.0 (#?(:clj Math/hypot :cljs js/Math.hypot) dx dy))]]
        {:pos   [(/ (+ x1 x2) 2.0) (/ (+ y1 y2) 2.0) 0.0]
         :color col
         :size  [len (double w)]
         :yaw   (#?(:clj Math/atan2 :cljs js/Math.atan2) dy dx)
         :metallic 0.0 :roughness 1.0 :emissive 0.0}))))

(defn board->render-ir
  "Board → ADR-0044 render-IR EDN. `screen` = [w h] (drives the camera framing).
   Rect items become billboard instances; connectors/ink become per-segment
   instances. z-ordered. The clear/horizon is nintendo-cream (KAMI §14)."
  ([board] (board->render-ir board [1280 720]))
  ([board [w h]]
   (let [items (b/items-z-asc board)
         rects (remove #(#{:connector :ink} (:item/kind %)) items)
         lines (filter #(#{:connector :ink} (:item/kind %)) items)]
     {:globals   {:horizon (vec (take 3 sc/nintendo-cream))
                  :sun-dir [0.0 0.0 -1.0] :sun [1.0 1.0 1.0]}
      :camera    {:eye    [(/ (double w) 2.0) (/ (double h) 2.0) 1000.0]
                  :target [(/ (double w) 2.0) (/ (double h) 2.0) 0.0]
                  :fov-y 1.05 :near 0.1 :far 5000.0}
      :instances (vec (concat (map item->instance rects)
                              (mapcat #(line->instances board %) lines)))})))
