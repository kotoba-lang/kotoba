(ns cad-import.xform
  "Minimal portable vec3 / quaternion / 4x4-affine-transform helpers.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930.

   The original Rust crate leaned on the `glam` crate (`Vec3`, `Quat`,
   `Mat4`) for AABB-corner transforms in `src/ingest/gltf.rs` and
   `src/ingest/scad.rs`. `glam` is not portable to CLJC, so this
   namespace implements the small subset of vector / quaternion / affine
   TRS math those two ingest adapters actually use, as plain data
   (`[x y z]` triples, 3x3 row-major matrices as `[[..][..][..]]`) and
   pure functions. Zero external dependencies, per ADR-2607010930.

   An *affine transform* here is `{:linear 3x3-matrix :translation v3}`
   — `linear` folds scale + rotation into one 3x3 matrix (as
   `glam::Mat4::from_scale_rotation_translation` does internally), so
   applying a point is a single matrix-vector multiply plus a
   translation, and composing two transforms (parent ∘ child, i.e.
   `parent_world * node_local_transform` in the original glTF walk) is a
   single matrix multiply.")

;; ---- vec3 ([x y z] triples) ----

(defn v3-add [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn v3-sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn v3-scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn v3-min [[ax ay az] [bx by bz]] [(min ax bx) (min ay by) (min az bz)])
(defn v3-max [[ax ay az] [bx by bz]] [(max ax bx) (max ay by) (max az bz)])
(defn v3-length [[x y z]] (Math/sqrt (+ (* x x) (* y y) (* z z))))
(def v3-inf [##Inf ##Inf ##Inf])
(def v3-neg-inf [##-Inf ##-Inf ##-Inf])
(def v3-zero [0.0 0.0 0.0])

;; ---- quaternion (xyzw) ----

(defn quat-identity [] [0.0 0.0 0.0 1.0])

(defn quat->rot3
  "3x3 rotation matrix (row-major: 3 rows, each `[m0 m1 m2]`) for the
   xyzw quaternion `[x y z w]`. Mirrors `glam::Mat4::from_quat`'s
   rotation block."
  [[x y z w]]
  (let [x2 (+ x x) y2 (+ y y) z2 (+ z z)
        xx (* x x2) xy (* x y2) xz (* x z2)
        yy (* y y2) yz (* y z2) zz (* z z2)
        wx (* w x2) wy (* w y2) wz (* w z2)]
    [[(- 1.0 (+ yy zz)) (- xy wz) (+ xz wy)]
     [(+ xy wz) (- 1.0 (+ xx zz)) (- yz wx)]
     [(- xz wy) (+ yz wx) (- 1.0 (+ xx yy))]]))

;; ---- 3x3 matrix helpers ----

(defn mat3-identity [] [[1.0 0.0 0.0] [0.0 1.0 0.0] [0.0 0.0 1.0]])

(defn mat3-scale
  "Diagonal scale matrix for `[sx sy sz]`."
  [[sx sy sz]]
  [[sx 0.0 0.0] [0.0 sy 0.0] [0.0 0.0 sz]])

(defn mat3-mul
  "3x3 row-major matrix product `a * b`."
  [a b]
  (vec
   (for [i (range 3)]
     (vec
      (for [j (range 3)]
        (reduce + (for [k (range 3)] (* (nth (nth a i) k) (nth (nth b k) j)))))))))

(defn mat3-mul-v3
  "3x3 matrix (row-major) times a column vector `[x y z]`."
  [m [x y z]]
  (vec (for [row m] (+ (* (nth row 0) x) (* (nth row 1) y) (* (nth row 2) z)))))

;; ---- affine transform: {:linear 3x3 :translation v3} ----

(defn affine-identity []
  {:linear (mat3-identity) :translation v3-zero})

(defn trs->affine
  "Build an affine transform from scale / rotation (xyzw quat) /
   translation — same semantics as
   `glam::Mat4::from_scale_rotation_translation`."
  [scale rotation translation]
  {:linear (mat3-mul (quat->rot3 (or rotation (quat-identity)))
                      (mat3-scale (or scale [1.0 1.0 1.0])))
   :translation (or translation v3-zero)})

(defn transform-point
  "Apply an affine transform to a point `[x y z]`: `linear * p + translation`."
  [{:keys [linear translation]} p]
  (v3-add (mat3-mul-v3 linear p) translation))

(defn compose-affine
  "Compose two affine transforms so that applying the result to a point
   equals `(transform-point parent (transform-point child p))` — i.e.
   `parent_world * node_local_transform(node)` in the original glTF
   walk."
  [parent child]
  {:linear (mat3-mul (:linear parent) (:linear child))
   :translation (v3-add (mat3-mul-v3 (:linear parent) (:translation child))
                         (:translation parent))})

(defn aabb-corners
  "8 corners of an axis-aligned box given `lo` / `hi` `[x y z]` corners,
   in the fixed corner order used throughout the crate (matches
   `VehiclePart::aabb_corners` in `part.rs`):
   0=lo 1=(hi.x,lo.y,lo.z) 2=(hi.x,hi.y,lo.z) 3=(lo.x,hi.y,lo.z)
   4=(lo.x,lo.y,hi.z) 5=(hi.x,lo.y,hi.z) 6=hi 7=(lo.x,hi.y,hi.z)."
  [[lx ly lz] [hx hy hz]]
  [[lx ly lz] [hx ly lz] [hx hy lz] [lx hy lz]
   [lx ly hz] [hx ly hz] [hx hy hz] [lx hy hz]])

(defn world-aabb-of-local-corners
  "World-space AABB (as `[lo hi]`) of a seq of local-space points after
   applying affine transform `xf` to each."
  [xf local-corners]
  (reduce (fn [[lo hi] p]
            (let [w (transform-point xf p)]
              [(v3-min lo w) (v3-max hi w)]))
          [v3-inf v3-neg-inf]
          local-corners))
