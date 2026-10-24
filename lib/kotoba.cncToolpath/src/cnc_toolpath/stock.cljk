(ns cnc-toolpath.stock
  "Workpiece stock definitions and material presets. Restored from
  kami-cam's `stock` module (deleted PR #82). A DVec3 point is a plain
  `[x y z]` vector.")

(defn block-shape [width height depth] {:kind :block :width width :height height :depth depth})
(defn cylinder-shape [diameter length] {:kind :cylinder :diameter diameter :length length})
(defn from-mesh-shape [vertices indices] {:kind :from-mesh :vertices (vec vertices) :indices (vec indices)})

(defn cam-material [name density hardness] {:name name :density density :hardness hardness})

(defn aluminum-6061 [] (cam-material "Aluminum 6061-T6" 2.70 95.0))
(defn steel-1045 [] (cam-material "Steel 1045" 7.87 163.0))
(defn titanium-ti6al4v [] (cam-material "Titanium Ti-6Al-4V" 4.43 334.0))
(defn abs-plastic [] (cam-material "ABS Plastic" 1.04 10.0))
(defn wood-oak [] (cam-material "Oak (Red)" 0.66 6.0))

(defn stock
  ([shape material] (stock shape material [0.0 0.0 0.0]))
  ([shape material origin] {:shape shape :material material :origin origin}))

(defn with-origin [s origin] (assoc s :origin origin))

(defn- vmin [[ax ay az] [bx by bz]] [(min ax bx) (min ay by) (min az bz)])
(defn- vmax [[ax ay az] [bx by bz]] [(max ax bx) (max ay by) (max az bz)])
(defn- vsub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])

(defn dimensions
  "Axis-aligned bounding box `[width height depth]` of the stock's shape.
  For `:from-mesh`, computed from vertex extents."
  [s]
  (let [shape (:shape s)]
    (case (:kind shape)
      :block [(:width shape) (:height shape) (:depth shape)]
      :cylinder [(:diameter shape) (:diameter shape) (:length shape)]
      :from-mesh
      (let [vs (:vertices shape)]
        (if (empty? vs)
          [0.0 0.0 0.0]
          (vsub (reduce vmax (first vs) (rest vs)) (reduce vmin (first vs) (rest vs))))))))
