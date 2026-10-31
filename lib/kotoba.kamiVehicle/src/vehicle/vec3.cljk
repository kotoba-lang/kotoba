(ns vehicle.vec3
  "Minimal 3-vector math utility, standing in for Rust's `glam::Vec3`.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   A vec3 is represented as a plain map `{:x _ :y _ :z _}` for portability
   across CLJ/CLJS/babashka without any external dependency.")

(defn v3
  ([] {:x 0.0 :y 0.0 :z 0.0})
  ([x y z] {:x (double x) :y (double y) :z (double z)}))

(def zero (v3 0.0 0.0 0.0))
(def unit-x (v3 1.0 0.0 0.0))
(def unit-y (v3 0.0 1.0 0.0))
(def unit-z (v3 0.0 0.0 1.0))
(def neg-unit-z (v3 0.0 0.0 -1.0))

(defn add [a b] (v3 (+ (:x a) (:x b)) (+ (:y a) (:y b)) (+ (:z a) (:z b))))
(defn sub [a b] (v3 (- (:x a) (:x b)) (- (:y a) (:y b)) (- (:z a) (:z b))))
(defn scale [a s] (v3 (* (:x a) s) (* (:y a) s) (* (:z a) s)))
(defn neg [a] (scale a -1.0))
(defn dot [a b] (+ (* (:x a) (:x b)) (* (:y a) (:y b)) (* (:z a) (:z b))))
(defn cross [a b]
  (v3 (- (* (:y a) (:z b)) (* (:z a) (:y b)))
      (- (* (:z a) (:x b)) (* (:x a) (:z b)))
      (- (* (:x a) (:y b)) (* (:y a) (:x b)))))
(defn length-sq [a] (dot a a))
(defn length [a] (Math/sqrt (length-sq a)))

(defn normalize-or-zero [a]
  (let [l (length a)]
    (if (> l 1e-12) (scale a (/ 1.0 l)) zero)))

(defn lerp [a b t] (add a (scale (sub b a) t)))

(defn finite? [a]
  #?(:clj (every? (fn [v] (and (not (Double/isNaN v)) (not (Double/isInfinite v))))
                   [(:x a) (:y a) (:z a)])
     :cljs (every? js/isFinite [(:x a) (:y a) (:z a)])))

(defn abs-max-element [a]
  (max (Math/abs (:x a)) (Math/abs (:y a)) (Math/abs (:z a))))

;; ---- 3x3 matrix helpers (column-major, mirroring glam::Mat3) ----
;; A mat3 is `{:c0 v3 :c1 v3 :c2 v3}` where each column is a vec3.

(def mat3-identity {:c0 unit-x :c1 unit-y :c2 unit-z})

(defn mat3-from-cols [c0 c1 c2] {:c0 c0 :c1 c1 :c2 c2})

(defn mat3-add [a b]
  (mat3-from-cols (add (:c0 a) (:c0 b)) (add (:c1 a) (:c1 b)) (add (:c2 a) (:c2 b))))

(defn mat3-sub [a b]
  (mat3-from-cols (sub (:c0 a) (:c0 b)) (sub (:c1 a) (:c1 b)) (sub (:c2 a) (:c2 b))))

(defn mat3-scale [a s]
  (mat3-from-cols (scale (:c0 a) s) (scale (:c1 a) s) (scale (:c2 a) s)))

(defn mat3-mul-vec3 [m v]
  ;; column-major: m * v = v.x * c0 + v.y * c1 + v.z * c2
  (add (add (scale (:c0 m) (:x v)) (scale (:c1 m) (:y v))) (scale (:c2 m) (:z v))))

(defn mat3-transpose [m]
  (let [c0 (:c0 m) c1 (:c1 m) c2 (:c2 m)]
    (mat3-from-cols (v3 (:x c0) (:x c1) (:x c2))
                     (v3 (:y c0) (:y c1) (:y c2))
                     (v3 (:z c0) (:z c1) (:z c2)))))

(defn mat3-determinant [m]
  (let [{:keys [c0 c1 c2]} m]
    (+ (* (:x c0) (- (* (:y c1) (:z c2)) (* (:z c1) (:y c2))))
       (- (* (:y c0) (- (* (:x c1) (:z c2)) (* (:z c1) (:x c2)))))
       (* (:z c0) (- (* (:x c1) (:y c2)) (* (:y c1) (:x c2)))))))

(defn mat3-inverse
  "Returns the inverse of `m`, or `nil` when singular. Uses the standard
   cross-product adjugate formula: with columns a,b,c, the inverse's ROWS
   are (b x c)/det, (c x a)/det, (a x b)/det; transposing those rows into
   columns gives the result below."
  [m]
  (let [{:keys [c0 c1 c2]} m
        det (mat3-determinant m)]
    (if (< (Math/abs det) 1e-12)
      nil
      (let [inv-det (/ 1.0 det)
            row0 (cross c1 c2)
            row1 (cross c2 c0)
            row2 (cross c0 c1)
            inv-c0 (v3 (:x row0) (:x row1) (:x row2))
            inv-c1 (v3 (:y row0) (:y row1) (:y row2))
            inv-c2 (v3 (:z row0) (:z row1) (:z row2))]
        (mat3-scale (mat3-from-cols inv-c0 inv-c1 inv-c2) inv-det)))))

(defn mat3-finite? [m]
  (and (finite? (:c0 m)) (finite? (:c1 m)) (finite? (:c2 m))))

(defn mat3-abs-diff [m]
  (max (abs-max-element (:c0 m)) (abs-max-element (:c1 m)) (abs-max-element (:c2 m))))

(defn mat3-from-rotation-y [theta]
  (let [s (Math/sin theta) c (Math/cos theta)]
    ;; glam Mat3::from_rotation_y column-major:
    ;; [ c 0 s; 0 1 0; -s 0 c ]  (rows), columns:
    (mat3-from-cols (v3 c 0.0 (- s))
                     (v3 0.0 1.0 0.0)
                     (v3 s 0.0 c))))
