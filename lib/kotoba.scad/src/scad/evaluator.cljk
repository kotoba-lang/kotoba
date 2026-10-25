(ns scad.evaluator
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-scad Rust crate
  (`kami-scad/src/evaluator.rs`, deleted in kotoba-lang/kami-engine PR #82 \"Remove
  Rust workspace from kami-engine\") as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  CSG tree evaluator: flattens a `scad.parser` AST into a vector of `ScadEntity`
  maps (`{:id :position :rotation :scale :primitive :color}`), each a single
  renderable primitive with its accumulated transform (translation / rotation
  quaternion / scale) and color. Transform composition is tracked as a 4x4
  column-major matrix (mirroring `glam::Mat4`), decomposed per-emit via a local
  port of `Mat4::to_scale_rotation_translation` + `Quat::from_mat3`.

  Difference/intersection are evaluated as union (visual approximation only,
  same Phase-1 simplification the original Rust carried: real boolean CSG mesh
  ops were left as a Phase-2 TODO in the deleted crate)."
  (:require [scad.parser :as parser]))

;; ---------------------------------------------------------------------------
;; Minimal portable Mat4 (column-major, glam-compatible layout) + Quat
;; ---------------------------------------------------------------------------
;; A mat4 is a flat 16-element vector, column-major: m[col*4 + row].

(defn- sqrt [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(defn- sin [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))
(defn- cos [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))
(defn- to-radians [deg] (* deg (/ #?(:clj Math/PI :cljs js/Math.PI) 180.0)))

(def mat4-identity
  [1.0 0.0 0.0 0.0
   0.0 1.0 0.0 0.0
   0.0 0.0 1.0 0.0
   0.0 0.0 0.0 1.0])

(defn mat4-from-translation [[tx ty tz]]
  [1.0 0.0 0.0 0.0
   0.0 1.0 0.0 0.0
   0.0 0.0 1.0 0.0
   tx  ty  tz  1.0])

(defn mat4-from-scale [[sx sy sz]]
  [sx  0.0 0.0 0.0
   0.0 sy  0.0 0.0
   0.0 0.0 sz  0.0
   0.0 0.0 0.0 1.0])

(defn mat4-from-quat
  "Rotation matrix from quaternion [x y z w] (glam::Mat4::from_quat formula)."
  [[x y z w]]
  (let [x2 (+ x x) y2 (+ y y) z2 (+ z z)
        xx (* x x2) xy (* x y2) xz (* x z2)
        yy (* y y2) yz (* y z2) zz (* z z2)
        wx (* w x2) wy (* w y2) wz (* w z2)]
    [(- 1.0 (+ yy zz)) (+ xy wz) (- xz wy) 0.0
     (- xy wz) (- 1.0 (+ xx zz)) (+ yz wx) 0.0
     (+ xz wy) (- yz wx) (- 1.0 (+ xx yy)) 0.0
     0.0 0.0 0.0 1.0]))

(defn- m-at [m row col] (nth m (+ (* col 4) row)))

(defn mat4-mul
  "a * b, both column-major flat 16-vectors."
  [a b]
  (vec (for [col (range 4) row (range 4)]
         (reduce + (for [k (range 4)] (* (m-at a row k) (m-at b k col)))))))

(defn quat-mul
  "Hamilton product a*b, both [x y z w]."
  [[ax ay az aw] [bx by bz bw]]
  [(+ (* aw bx) (* ax bw) (* ay bz) (- (* az by)))
   (+ (- (* aw by) (* ax bz)) (* ay bw) (* az bx))
   (+ (* aw bz) (* ax by) (- (* ay bx)) (* az bw))
   (- (* aw bw) (* ax bx) (* ay by) (* az bz))])

(defn quat-from-rotation-x [angle-deg]
  (let [half (/ (to-radians angle-deg) 2.0)]
    [(sin half) 0.0 0.0 (cos half)]))

(defn quat-from-rotation-y [angle-deg]
  (let [half (/ (to-radians angle-deg) 2.0)]
    [0.0 (sin half) 0.0 (cos half)]))

(defn quat-from-rotation-z [angle-deg]
  (let [half (/ (to-radians angle-deg) 2.0)]
    [0.0 0.0 (sin half) (cos half)]))

(defn- vec3-len [[x y z]] (sqrt (+ (* x x) (* y y) (* z z))))

(defn- cross3 [[a1 a2 a3] [b1 b2 b3]]
  [(- (* a2 b3) (* a3 b2))
   (- (* a3 b1) (* a1 b3))
   (- (* a1 b2) (* a2 b1))])

(defn- dot3 [[a1 a2 a3] [b1 b2 b3]] (+ (* a1 b1) (* a2 b2) (* a3 b3)))

(defn- det3
  "Determinant of the 3x3 matrix whose columns are c0 c1 c2 (each [x y z])."
  [c0 c1 c2]
  (dot3 c0 (cross3 c1 c2)))

(defn- signum [x] (cond (pos? x) 1.0 (neg? x) -1.0 :else 0.0))

(defn- quat-from-mat3
  "Rotation matrix -> quaternion [x y z w], columns c0 c1 c2 each [x y z]
  (Shepperd's method, standard rotation-matrix-to-quaternion conversion)."
  [[m00 m10 m20] [m01 m11 m21] [m02 m12 m22]]
  (let [trace (+ m00 m11 m22)]
    (cond
      (> trace 0.0)
      (let [s (* (sqrt (+ trace 1.0)) 2.0)]
        [(/ (- m21 m12) s) (/ (- m02 m20) s) (/ (- m10 m01) s) (/ s 4.0)])

      (and (> m00 m11) (> m00 m22))
      (let [s (* (sqrt (+ 1.0 (- m00 m11) (- m22))) 2.0)]
        [(/ s 4.0) (/ (+ m01 m10) s) (/ (+ m02 m20) s) (/ (- m21 m12) s)])

      (> m11 m22)
      (let [s (* (sqrt (+ 1.0 (- m11 m00) (- m22))) 2.0)]
        [(/ (+ m01 m10) s) (/ s 4.0) (/ (+ m12 m21) s) (/ (- m02 m20) s)])

      :else
      (let [s (* (sqrt (+ 1.0 (- m22 m00) (- m11))) 2.0)]
        [(/ (+ m02 m20) s) (/ (+ m12 m21) s) (/ s 4.0) (/ (- m10 m01) s)]))))

(defn mat4-decompose
  "Decompose an affine mat4 -> {:translation [x y z] :rotation [x y z w]
  :scale [x y z]}, mirroring glam's Mat4::to_scale_rotation_translation."
  [m]
  (let [x-axis [(m-at m 0 0) (m-at m 1 0) (m-at m 2 0)]
        y-axis [(m-at m 0 1) (m-at m 1 1) (m-at m 2 1)]
        z-axis [(m-at m 0 2) (m-at m 1 2) (m-at m 2 2)]
        w-axis [(m-at m 0 3) (m-at m 1 3) (m-at m 2 3)]
        det (det3 x-axis y-axis z-axis)
        sx (* (vec3-len x-axis) (signum det))
        sy (vec3-len y-axis)
        sz (vec3-len z-axis)
        inv-sx (if (zero? sx) 0.0 (/ 1.0 sx))
        inv-sy (if (zero? sy) 0.0 (/ 1.0 sy))
        inv-sz (if (zero? sz) 0.0 (/ 1.0 sz))
        rc0 (mapv #(* % inv-sx) x-axis)
        rc1 (mapv #(* % inv-sy) y-axis)
        rc2 (mapv #(* % inv-sz) z-axis)
        rotation (quat-from-mat3 rc0 rc1 rc2)]
    {:translation w-axis :rotation rotation :scale [sx sy sz]}))

;; ---------------------------------------------------------------------------
;; Evaluator
;; ---------------------------------------------------------------------------

(defn- new-ctx []
  (atom {:transform mat4-identity
         :color [0.5 0.5 0.5 1.0]
         :entities []
         :counter 0
         :modules {}}))

(defn- next-id! [ctx]
  (swap! ctx update :counter inc)
  (str "scad-" (:counter @ctx)))

(defn- emit! [ctx primitive]
  (let [{:keys [translation rotation scale]} (mat4-decompose (:transform @ctx))
        id (next-id! ctx)
        color (:color @ctx)]
    (swap! ctx update :entities conj
           {:id id :position translation :rotation rotation :scale scale
            :primitive primitive :color color})))

(declare eval-node! eval-nodes!)

(defn- eval-nodes! [ctx nodes]
  (doseq [node nodes] (eval-node! ctx node)))

(defn- eval-node! [ctx node]
  (case (:type node)
    :sphere
    (emit! ctx {:type :sphere :radius (:r node)})

    :cube
    (let [{:keys [size center]} node]
      (if-not center
        (let [saved (:transform @ctx)
              [sx sy sz] size]
          (swap! ctx assoc :transform
                 (mat4-mul saved (mat4-from-translation [(/ sx 2.0) (/ sy 2.0) (/ sz 2.0)])))
          (emit! ctx {:type :cube :size size :center true})
          (swap! ctx assoc :transform saved))
        (emit! ctx {:type :cube :size size :center true})))

    :cylinder
    (let [{:keys [h r1 r2 center]} node]
      (if-not center
        (let [saved (:transform @ctx)]
          (swap! ctx assoc :transform
                 (mat4-mul saved (mat4-from-translation [0.0 (/ h 2.0) 0.0])))
          (emit! ctx {:type :cylinder :h h :r1 r1 :r2 r2 :center true})
          (swap! ctx assoc :transform saved))
        (emit! ctx {:type :cylinder :h h :r1 r1 :r2 r2 :center true})))

    :translate
    (let [saved (:transform @ctx)]
      (swap! ctx assoc :transform (mat4-mul saved (mat4-from-translation (:v node))))
      (eval-nodes! ctx (:children node))
      (swap! ctx assoc :transform saved))

    :rotate
    (let [saved (:transform @ctx)
          [vx vy vz] (:v node)
          rx (quat-from-rotation-x vx)
          ry (quat-from-rotation-y vy)
          rz (quat-from-rotation-z vz)
          rotation (quat-mul (quat-mul rz ry) rx)]
      (swap! ctx assoc :transform (mat4-mul saved (mat4-from-quat rotation)))
      (eval-nodes! ctx (:children node))
      (swap! ctx assoc :transform saved))

    :scale
    (let [saved (:transform @ctx)]
      (swap! ctx assoc :transform (mat4-mul saved (mat4-from-scale (:v node))))
      (eval-nodes! ctx (:children node))
      (swap! ctx assoc :transform saved))

    :color
    (let [saved-color (:color @ctx)]
      (swap! ctx assoc :color (:rgba node))
      (eval-nodes! ctx (:children node))
      (swap! ctx assoc :color saved-color))

    (:union :block)
    (eval-nodes! ctx (:children node))

    (:difference :intersection)
    ;; Phase 1: treat as union (visual approximation). Phase 2: implement
    ;; BSP-tree CSG boolean mesh operations. (unchanged from original TODO)
    (eval-nodes! ctx (:children node))

    :module-def
    (swap! ctx assoc-in [:modules (:name node)] (:body node))

    :module-call
    (when-let [body (get (:modules @ctx) (:name node))]
      (eval-nodes! ctx body))

    nil))

(defn evaluate
  "Evaluate OpenSCAD source `src` into a vector of renderable `ScadEntity`
  maps: `{:id :position :rotation :scale :primitive :color}`."
  [src]
  (let [nodes (parser/parse src)
        ctx (new-ctx)]
    (eval-nodes! ctx nodes)
    (:entities @ctx)))
