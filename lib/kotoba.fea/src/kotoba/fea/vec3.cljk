(ns kotoba.fea.vec3
  "Minimal pure 3-vector math over `[x y z]` (plain 3-element vectors of
  doubles) — the cljc equivalent of `glam::DVec3`, which kami-cae
  (kami-engine, now retired per ADR-2607010000) used for node positions,
  displacements and directions. No network, no I/O.")

(def zero [0.0 0.0 0.0])

(defn add [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])

(defn sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])

(defn scale [[x y z] s] [(* x s) (* y s) (* z s)])

(defn dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))

(defn sqrt* [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))

(defn abs* [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))

(defn length-sq [v] (dot v v))

(defn length [v] (sqrt* (length-sq v)))

(defn normalize
  "Unit vector in the direction of `v`. Undefined (division by ~0) for a
  zero-length `v` — callers must guard, matching kami-cae's own `length <
  1e-15` guards at call sites."
  [v]
  (scale v (/ 1.0 (length v))))
