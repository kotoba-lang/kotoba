(ns kotoba.geo.vec3
  "Minimal 3-vector math shared by `kotoba.geo.mesh`.

  Vectors are plain 3-element vectors `[x y z]`. Ported from the small
  free-function vec helpers at the bottom of kami-geo's `mesh.rs`
  (`add3`/`sub3`/`mul3`/`cross3`/`normalize3`)."
  (:require [kotoba.geo.math :as math]))

(defn add [[ax ay az] [bx by bz]]
  [(+ ax bx) (+ ay by) (+ az bz)])

(defn sub [[ax ay az] [bx by bz]]
  [(- ax bx) (- ay by) (- az bz)])

(defn mul [[x y z] s]
  [(* x s) (* y s) (* z s)])

(defn cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by))
   (- (* az bx) (* ax bz))
   (- (* ax by) (* ay bx))])

(defn length [[x y z]]
  (math/sqrt (+ (* x x) (* y y) (* z z))))

(defn normalize [[x y z :as v]]
  (let [len (max (length v) 1e-6)]
    [(/ x len) (/ y len) (/ z len)]))
