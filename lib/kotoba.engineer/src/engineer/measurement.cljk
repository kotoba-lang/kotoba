(ns engineer.measurement
  "Distance/angle/area/volume measurement helpers. Restored from
  kami-eng-core's `measurement` module (deleted PR #82). Points are `[x y z]`
  3-vectors (glam::DVec3 in the original).")

(defn- v- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- v-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn- v-len [v] (Math/sqrt (v-dot v v)))
(defn- v-normalize [v] (let [l (v-len v)] (mapv #(/ % l) v)))
(defn- clamp [x lo hi] (max lo (min hi x)))

(defn distance-point-point
  "Distance between 3D points `a` and `b`. Returns a measure-result map."
  [a b]
  {:kind "distance" :value (v-len (v- b a)) :unit "mm" :points [a b]})

(defn angle-three-points
  "Angle (degrees) at `vertex` formed by rays to `a` and `c`."
  [a vertex c]
  (let [va (v-normalize (v- a vertex))
        vc (v-normalize (v- c vertex))
        angle-rad (Math/acos (clamp (v-dot va vc) -1.0 1.0))]
    {:kind "angle" :value (Math/toDegrees angle-rad) :unit "deg" :points [a vertex c]}))
