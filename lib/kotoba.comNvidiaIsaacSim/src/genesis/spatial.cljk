(ns genesis.spatial
  "6-D spatial-vector (\"Plucker\") algebra for the 3-D reduced-coordinate
  articulated-body solver class (Featherstone, *Rigid Body Dynamics
  Algorithms*, 2008, Ch. 2). Clean-room textbook math — no NVIDIA / PhysX /
  Isaac code is linked or referenced.

  Conventions:
    - A spatial *motion* vector is `[wx wy wz vx vy vz]` (angular on top,
      linear at the frame origin).
    - A spatial *force* vector is `[nx ny nz fx fy fz]` (moment on top,
      linear).
    - Transforms / inertias / cross-products are explicit 6x6 matrices
      represented as vectors-of-6-row-vectors (row-major).

  Restored from kotoba-lang/kami-engine `kami-genesis/src/spatial.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math)."
  (:require [genesis.vec3 :as v3]))

(def zero-sv [0.0 0.0 0.0 0.0 0.0 0.0])
(def zero-m6 (vec (repeat 6 (vec (repeat 6 0.0)))))

(defn mat3-mul
  "3x3 * 3x3, each matrix as [[r0] [r1] [r2]] row-major."
  [a b]
  (vec (for [i (range 3)]
         (vec (for [j (range 3)]
                (reduce + (for [k (range 3)] (* (get-in a [i k]) (get-in b [k j])))))))))

(defn mat3-vec [m v]
  (vec (for [i (range 3)] (v3/dot (nth m i) v))))

(defn mat3-transpose [m]
  (vec (for [j (range 3)] (vec (for [i (range 3)] (get-in m [i j]))))))

(defn mat3-sub [a b]
  (vec (for [i (range 3)] (vec (for [j (range 3)] (- (get-in a [i j]) (get-in b [i j])))))))

(defn mat3-scale [m s]
  (vec (for [row m] (mapv #(* % s) row))))

(def mat3-zero [[0.0 0.0 0.0] [0.0 0.0 0.0] [0.0 0.0 0.0]])
(def mat3-identity [[1.0 0.0 0.0] [0.0 1.0 0.0] [0.0 0.0 1.0]])

(defn skew
  "Skew-symmetric matrix [v]x such that [v]x * w = v cross w."
  [[vx vy vz]]
  [[0.0 (- vz) vy]
   [vz 0.0 (- vx)]
   [(- vy) vx 0.0]])

(defn from-blocks
  "Assemble a 6x6 from four 3x3 blocks: [[tl tr] [bl br]]."
  [tl tr bl br]
  (vec (concat
         (for [r (range 3)] (vec (concat (nth tl r) (nth tr r))))
         (for [r (range 3)] (vec (concat (nth bl r) (nth br r)))))))

(defn sv [[tx ty tz] [bx by bz]] [tx ty tz bx by bz])
(defn sv-top [s] (subvec s 0 3))
(defn sv-bot [s] (subvec s 3 6))

(defn mat-vec [m v]
  (vec (for [r (range 6)] (reduce + (map * (nth m r) v)))))

(defn mat-mul [a b]
  (vec (for [r (range 6)]
         (vec (for [c (range 6)]
                (reduce + (for [k (range 6)] (* (get-in a [r k]) (get-in b [k c])))))))))

(defn transpose [a]
  (vec (for [c (range 6)] (vec (for [r (range 6)] (get-in a [r c]))))))

(defn m-add [a b]
  (vec (for [r (range 6)] (vec (map + (nth a r) (nth b r))))))

(defn sv-dot [a b] (reduce + (map * a b)))

(defn axpy [scale x y]
  (vec (map (fn [xi yi] (+ (* scale xi) yi)) x y)))

(defn plucker
  "Plucker motion transform X built from a child frame whose orientation
  is `e` (3x3) and whose origin sits at `r` (world vec3) in the parent
  frame. X * m_parent = m_child. Force transform up the tree is X^T."
  [e r]
  (let [neg-e-rx (mat3-scale (mat3-mul e (skew r)) -1.0)]
    (from-blocks e mat3-zero neg-e-rx e)))

(defn plucker-inv
  "Inverse of plucker(e, r): plucker(e^T, -(e*r))."
  [e r]
  (plucker (mat3-transpose e) (v3/neg (mat3-vec e r))))

(defn spatial-inertia
  "Spatial inertia (6x6) of a body with mass `m`, centre of mass `c`, and
  rotational inertia `i-c` (3x3) about the COM."
  [m c i-c]
  (let [cx (skew c)
        tl (mat3-sub i-c (mat3-scale (mat3-mul cx cx) m))
        tr (mat3-scale cx m)
        bl (mat3-scale cx (- m))
        br (mat3-scale mat3-identity m)]
    (from-blocks tl tr bl br)))

(defn crm
  "Motion cross-product matrix crm(v) s.t. crm(v)*s = v xm s."
  [v]
  (let [w (skew (sv-top v)) u (skew (sv-bot v))]
    (from-blocks w mat3-zero u w)))

(defn crf
  "Force cross-product matrix crf(v) = -crm(v)^T s.t. crf(v)*f = v xf f."
  [v]
  (let [w (skew (sv-top v)) u (skew (sv-bot v))]
    (from-blocks w u mat3-zero w)))
