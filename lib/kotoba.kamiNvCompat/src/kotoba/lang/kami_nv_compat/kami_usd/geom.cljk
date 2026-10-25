(ns kotoba.lang.kami-nv-compat.kami-usd.geom
  "kami-usd geometry bridge — USDA prim tree -> kami-rt triangles +
  materials. Portable .cljc port of src/kami-usd/geom.ts. Wave 30.

  Triangulates UsdGeomMesh prims (fan triangulation over
  faceVertexCounts), composes the hierarchical Xform stack into a world
  matrix, and extracts a Lambertian material from displayColor /
  emissive primvars. The output feeds directly into kami-rt build-scene
  (ray) and kami-rtx build-path-scene (path trace).

  ADR-2605261800 SD6 / D10.4 kami-usd."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.pathtrace :as pt]))

;; ── row-major 4x4 matrix (point' = M . [x y z 1]) ────────────────────────
;; Mat4 = a 16-element vector, row-major.

(defn identity4 []
  [1.0 0.0 0.0 0.0
   0.0 1.0 0.0 0.0
   0.0 0.0 1.0 0.0
   0.0 0.0 0.0 1.0])

(defn mul4
  [a b]
  (vec (for [r (range 4) c (range 4)]
         (reduce + (for [k (range 4)] (* (a (+ (* r 4) k)) (b (+ (* k 4) c))))))))

(defn transform-point
  [m p]
  [(+ (* (m 0) (p 0)) (* (m 1) (p 1)) (* (m 2) (p 2)) (m 3))
   (+ (* (m 4) (p 0)) (* (m 5) (p 1)) (* (m 6) (p 2)) (m 7))
   (+ (* (m 8) (p 0)) (* (m 9) (p 1)) (* (m 10) (p 2)) (m 11))])

(defn- translate4
  [t]
  [1.0 0.0 0.0 (t 0)
   0.0 1.0 0.0 (t 1)
   0.0 0.0 1.0 (t 2)
   0.0 0.0 0.0 1.0])

(defn- scale4
  [s]
  [(s 0) 0.0 0.0 0.0
   0.0 (s 1) 0.0 0.0
   0.0 0.0 (s 2) 0.0
   0.0 0.0 0.0 1.0])

(defn- rot-x
  [deg]
  (let [a (/ (* deg Math/PI) 180.0)
        c (Math/cos a)
        s (Math/sin a)]
    [1.0 0.0 0.0 0.0
     0.0 c (- s) 0.0
     0.0 s c 0.0
     0.0 0.0 0.0 1.0]))

(defn- rot-y
  [deg]
  (let [a (/ (* deg Math/PI) 180.0)
        c (Math/cos a)
        s (Math/sin a)]
    [c 0.0 s 0.0
     0.0 1.0 0.0 0.0
     (- s) 0.0 c 0.0
     0.0 0.0 0.0 1.0]))

(defn- rot-z
  [deg]
  (let [a (/ (* deg Math/PI) 180.0)
        c (Math/cos a)
        s (Math/sin a)]
    [c (- s) 0.0 0.0
     s c 0.0 0.0
     0.0 0.0 1.0 0.0
     0.0 0.0 0.0 1.0]))

;; ── value coercion helpers ────────────────────────────────────────────────

(defn- to-number
  [v]
  (cond
    (number? v) (double v)
    (true? v) 1.0
    (false? v) 0.0
    (string? v) #?(:clj (try (Double/parseDouble v) (catch Exception _ 0.0))
                   :cljs (let [n (js/parseFloat v)] (if (js/isNaN n) 0.0 n)))
    :else 0.0))

(defn- as-vec3
  [v fallback]
  (if (and (vector? v) (>= (count v) 3))
    [(to-number (v 0)) (to-number (v 1)) (to-number (v 2))]
    fallback))

(defn- prim-attr
  "Read an attribute value by name (nil when absent)."
  [prim attr-name]
  (get-in prim [:attributes attr-name :value]))

;; ── Xform op composition ─────────────────────────────────────────────────

(defn- op-matrix
  [prim op]
  (let [v (prim-attr prim op)]
    (cond
      (= op "xformOp:translate") (translate4 (as-vec3 v [0.0 0.0 0.0]))
      (= op "xformOp:scale") (scale4 (as-vec3 v [1.0 1.0 1.0]))
      (= op "xformOp:rotateXYZ")
      (let [e (as-vec3 v [0.0 0.0 0.0])]
        (mul4 (rot-x (e 0)) (mul4 (rot-y (e 1)) (rot-z (e 2)))))
      (= op "xformOp:rotateX") (rot-x (if (number? v) v 0.0))
      (= op "xformOp:rotateY") (rot-y (if (number? v) v 0.0))
      (= op "xformOp:rotateZ") (rot-z (if (number? v) v 0.0))
      (and (= op "xformOp:transform") (vector? v))
      (let [flat (vec (mapcat (fn [e] (if (vector? e) (map to-number e) [(to-number e)])) v))]
        (if (= 16 (count flat)) flat (identity4)))
      :else (identity4))))

(defn local-transform
  "Local transform of a prim from its xformOp stack. xformOpOrder lists ops
  outermost-first; the matrix is their product in that order. With no order
  attribute, present ops apply as translate . rotate . scale (SRT)."
  [prim]
  (let [order-raw (prim-attr prim "xformOpOrder")
        order (if (vector? order-raw)
                (mapv str order-raw)
                (filterv #(contains? (:attributes prim) %)
                         ["xformOp:translate" "xformOp:rotateXYZ" "xformOp:scale"]))]
    (reduce (fn [m op] (mul4 m (op-matrix prim op))) (identity4) order)))

;; ── material extraction ──────────────────────────────────────────────────

(def default-albedo [0.8 0.8 0.8])

(defn- first-color
  [v]
  (when (vector? v)
    (cond
      (vector? (v 0)) (as-vec3 (v 0) default-albedo)
      (and (>= (count v) 3) (number? (v 0))) [(to-number (v 0)) (to-number (v 1)) (to-number (v 2))]
      :else nil)))

(defn mesh-material
  [prim]
  (let [albedo (or (first-color (prim-attr prim "primvars:displayColor"))
                    (first-color (prim-attr prim "inputs:diffuseColor"))
                    default-albedo)
        emission (or (first-color (prim-attr prim "primvars:emissiveColor"))
                     (first-color (prim-attr prim "inputs:emissiveColor"))
                     [0.0 0.0 0.0])]
    (pt/material albedo emission)))

;; ── mesh triangulation ────────────────────────────────────────────────────

(defn- read-points
  [prim]
  (let [v (prim-attr prim "points")]
    (if (vector? v) (mapv #(as-vec3 % [0.0 0.0 0.0]) v) [])))

(defn- read-int-array
  [prim attr-name]
  (let [v (prim-attr prim attr-name)]
    (if (vector? v) (mapv to-number v) [])))

(defn triangulate-mesh
  "Triangulate one UsdGeomMesh prim into world-space triangles. Polygons are
  fan-triangulated; if faceVertexCounts is absent the index stream is taken
  as consecutive triangles."
  [prim world]
  (let [points (mapv #(transform-point world %) (read-points prim))
        indices (read-int-array prim "faceVertexIndices")
        counts0 (read-int-array prim "faceVertexCounts")]
    (if (or (empty? indices) (empty? points))
      []
      (let [counts (if (empty? counts0)
                     (vec (repeat (quot (count indices) 3) 3))
                     counts0)]
        (loop [cs counts cursor 0 tris []]
          (if (empty? cs)
            tris
            (let [n (int (first cs))
                  tris2 (if (and (>= n 3) (<= (+ cursor n) (count indices)))
                          (let [v0 (points (int (indices cursor)))]
                            (into tris
                                  (for [k (range 1 (dec n))
                                        :let [v1 (points (int (indices (+ cursor k))))
                                              v2 (points (int (indices (+ cursor k 1))))]
                                        :when (and v0 v1 v2)]
                                    [v0 v1 v2])))
                          tris)]
              (recur (rest cs) (+ cursor n) tris2))))))))

;; ── stage flatten ─────────────────────────────────────────────────────────

(defn flatten-stage
  "Walk a USDA prim tree, accumulating world transforms, and collect every
  UsdGeomMesh as world-space triangles + a per-triangle material. Returns
  {:triangles :materials}."
  [roots]
  (let [triangles (atom [])
        materials (atom [])]
    (letfn [(walk [prim parent-world]
              (let [world (mul4 parent-world (local-transform prim))]
                (when (= "Mesh" (:type-name prim))
                  (let [mat (mesh-material prim)]
                    (doseq [t (triangulate-mesh prim world)]
                      (swap! triangles conj t)
                      (swap! materials conj mat))))
                (doseq [child (:children prim)] (walk child world))))]
      (doseq [r roots] (walk r (identity4))))
    {:triangles @triangles :materials @materials}))
