(ns kotoba.live.vec3
  "Minimal 3-vector helpers — `[x y z]` triples, pure functions, no I/O.

  Small and local to `kotoba.live` rather than a dependency on a general math
  library: the domain only needs add/sub/scale/lerp/normalize."
  (:require [kotoba.live.mathx :as mathx]))

(def zero [0.0 0.0 0.0])

(defn v+ [a b] (mapv + a b))
(defn v- [a b] (mapv - a b))
(defn v*s [v s] (mapv #(* % s) v))
(defn dot [a b] (reduce + (map * a b)))
(defn len [v] (mathx/sqrt (dot v v)))

(defn normalize
  "Unit vector in the direction of `v`. Returns `v` unchanged if it is
  (numerically) the zero vector."
  [v]
  (let [n (len v)]
    (if (zero? n) v (v*s v (/ 1.0 n)))))

(defn lerp
  "Linear interpolation between 3-vectors `a` and `b` at `t` in [0,1]."
  [a b t]
  (v+ a (v*s (v- b a) t)))
