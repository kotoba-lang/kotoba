(ns autodrive.geom
  "Portable planar (Vec2) and spatial (Vec3) vector math.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82) as part of ADR-2607010930's zero-dependency
  CLJC migration. The original crate used the `glam` crate for vector math;
  this namespace provides the plain-data equivalents needed by the rest of
  `autodrive.*` so the whole crate stays dependency-free.

  Vectors are plain maps `{:x _ :y _}` / `{:x _ :y _ :z _}` — no protocols, no
  records, just data plus pure functions.")

;; ─────────────────────────────── Vec2 ───────────────────────────────

(defn v2 [x y] {:x x :y y})

(def zero2 (v2 0.0 0.0))

(defn add2 [a b] (v2 (+ (:x a) (:x b)) (+ (:y a) (:y b))))
(defn sub2 [a b] (v2 (- (:x a) (:x b)) (- (:y a) (:y b))))
(defn scale2 [a s] (v2 (* (:x a) s) (* (:y a) s)))
(defn dot2 [a b] (+ (* (:x a) (:x b)) (* (:y a) (:y b))))
(defn length-sq2 [a] (dot2 a a))
(defn length2 [a] (Math/sqrt (length-sq2 a)))
(defn distance-sq2 [a b] (length-sq2 (sub2 a b)))
(defn distance2 [a b] (length2 (sub2 a b)))

(defn normalize2 [a]
  (let [l (length2 a)]
    (if (> l 1e-9) (scale2 a (/ 1.0 l)) a)))

(defn lerp2 [a b t] (add2 a (scale2 (sub2 b a) t)))

(defn splat2 [s] (v2 s s))

;; ─────────────────────────────── Vec3 ───────────────────────────────

(defn v3 [x y z] {:x x :y y :z z})

(def zero3 (v3 0.0 0.0 0.0))

(defn add3 [a b] (v3 (+ (:x a) (:x b)) (+ (:y a) (:y b)) (+ (:z a) (:z b))))
(defn sub3 [a b] (v3 (- (:x a) (:x b)) (- (:y a) (:y b)) (- (:z a) (:z b))))
(defn scale3 [a s] (v3 (* (:x a) s) (* (:y a) s) (* (:z a) s)))
(defn dot3 [a b] (+ (* (:x a) (:x b)) (* (:y a) (:y b)) (* (:z a) (:z b))))
(defn length-sq3 [a] (dot3 a a))
(defn length3 [a] (Math/sqrt (length-sq3 a)))
(defn distance3 [a b] (length3 (sub3 a b)))

(defn normalize3 [a]
  (let [l (length3 a)]
    (if (> l 1e-9) (scale3 a (/ 1.0 l)) a)))

(defn cross3 [a b]
  (v3 (- (* (:y a) (:z b)) (* (:z a) (:y b)))
      (- (* (:z a) (:x b)) (* (:x a) (:z b)))
      (- (* (:x a) (:y b)) (* (:y a) (:x b)))))

(defn finite? [x] #?(:clj (Double/isFinite (double x)) :cljs (js/isFinite x)))
