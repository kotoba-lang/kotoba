(ns kami-app-isekai.heightmap-color
  "Pure height -> RGB color mapping + grid sampling for visualizing
  `kami-app-isekai.voxel-world/terrain-height` as a top-down heightmap: low
  ground reads as deep blue, mid ground as grass green, high ground as
  near-white (snow-cap) — a presentation gloss on the same silhouette
  `terrain-voxel-at` already encodes (stone below h-3, grass below h, air
  above h). Zero-dep, portable CLJC — this is DATA/CONFIG, not a renderer;
  the actual GPU draw call lives in kotoba-lang/webgpu's `kami.sprite-gpu`
  (a test/demo-only sibling dep, see `test/render_pixel_test.clj` — this
  namespace itself has no dependency on it and is safe to `:require` from
  anywhere, cljs/wasm included).")

;; Gradient stops. Kept separate from voxel-world's `isekai-palette` (which
;; colors individual placed voxels by material) — this is a continuous
;; height gradient for a bird's-eye heightmap, not a per-voxel material.
(def color-low  [0.03 0.08 0.35])  ;; deep blue — low ground
(def color-mid  [0.20 0.55 0.20])  ;; grass green — mid ground
(def color-high [0.95 0.95 0.95])  ;; near-white — peaks

(defn- lerp [a b t] (+ a (* (- b a) t)))

(defn- lerp3 [[ar ag ab] [br bg bb] t]
  [(lerp ar br t) (lerp ag bg t) (lerp ab bb t)])

(defn height->color
  "Height (as returned by `voxel-world/terrain-height`) -> `[r g b]` each in
  [0,1]. Normalizes against the two bounds given (typically
  `voxel-world/terrain-height-min`/`-max`, the kernel's own analytic
  range), clamps to [0,1], then a 2-segment gradient: blue->green over the
  low half of the range, green->white over the high half. Monotonic in `h`
  along either half (each channel of `color-low`/`color-mid`/`color-high`
  is crossed by a single linear segment, never doubles back)."
  ([h] (height->color h 18.0 30.0))
  ([h height-min height-max]
   (let [t (-> (/ (- h height-min) (- height-max height-min))
               (max 0.0) (min 1.0))]
     (if (< t 0.5)
       (lerp3 color-low color-mid (* t 2.0))
       (lerp3 color-mid color-high (* (- t 0.5) 2.0))))))

(defn sample-grid
  "Sample `terrain-height-fn` (a `(wx wz) -> height` function, i.e.
  `voxel-world/terrain-height`) over an `n` x `n` grid of world (x,z)
  coordinates spaced `step` world-units apart, starting at world origin
  `[x0 z0]`. Returns a vector of `{:col :row :wx :wz :h :color}` maps — the
  data a renderer turns into colored quads (one per cell)."
  [terrain-height-fn {:keys [x0 z0 step n]}]
  (vec
   (for [row (range n) col (range n)
         :let [wx (+ x0 (* col step))
               wz (+ z0 (* row step))
               h  (terrain-height-fn wx wz)]]
     {:col col :row row :wx wx :wz wz :h h :color (height->color h)})))
