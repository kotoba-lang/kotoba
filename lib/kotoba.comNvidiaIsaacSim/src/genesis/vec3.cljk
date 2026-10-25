(ns genesis.vec3
  "Minimal portable 3-vector math (mirrors the subset of `glam::Vec3` used by
  the restored kami-genesis modules: obb, ccd, convex, spatial).

  Restored from kotoba-lang/kami-engine `kami-genesis` crate (deleted PR #82,
  \"Remove Rust workspace\") as zero-dependency portable CLJC.
  Per ADR-2607010930.

  Vectors are represented as `[x y z]` (3-element vectors of doubles)."
  #?(:cljs (:require [goog.object])))

(defn v3 [x y z] [x y z])
(def zero [0.0 0.0 0.0])
(def x-axis [1.0 0.0 0.0])
(def y-axis [0.0 1.0 0.0])
(def z-axis [0.0 0.0 1.0])

(defn add [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn neg [v] (scale v -1.0))
(defn dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by))
   (- (* az bx) (* ax bz))
   (- (* ax by) (* ay bx))])
(defn length-squared [v] (dot v v))
(defn length [v] (Math/sqrt (length-squared v)))
(defn normalize [v]
  (let [l (length v)]
    (if (< l 1e-12) zero (scale v (/ 1.0 l)))))
(defn normalize-or-zero [v]
  (let [l (length v)]
    (if (< l 1e-12) zero (scale v (/ 1.0 l)))))
