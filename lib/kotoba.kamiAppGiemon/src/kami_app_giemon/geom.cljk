(ns kami-app-giemon.geom
  "Minimal portable vec3/quaternion/transform kernel.

  Restored from `kami-engine/kami-app-giemon` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace\") as part of the clj-wgsl
  migration (ADR-2607010930, `com-junkawasaki/root`).

  The original crate built every part transform via `glam`'s
  `Mat4::from_scale_rotation_translation` + `Quat::from_rotation_x/z` +
  (for `segment_box`) `Quat::from_rotation_arc`. Rather than depend on a
  native linear-algebra crate, this namespace ports just those primitives
  as pure CLJC data + functions: a 3-vector is a `[x y z]` vector, a
  quaternion is `[x y z w]`, and a *transform* is a map of
  `{:scale [sx sy sz], :rotation quat, :translate [x y z]}` — the same
  three components `Mat4::from_scale_rotation_translation` takes, kept
  unflattened (rather than baked into a 4x4 matrix) since every
  restored geometry generator here only ever needs to know a part's
  scale/rotation/translation, or to transform a single point by it
  (used by tests to check ported geometry against the original math)."
  #?(:cljs (:require-macros [kami-app-giemon.geom])))

;; ── vec3 ─────────────────────────────────────────────────────────────────

(defn v3+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn v3- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn v3-scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn v3-hadamard [[ax ay az] [bx by bz]] [(* ax bx) (* ay by) (* az bz)])
(defn v3-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn v3-cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by))
   (- (* az bx) (* ax bz))
   (- (* ax by) (* ay bx))])
(defn v3-length [v] (Math/sqrt (v3-dot v v)))
(defn v3-normalize [v]
  (let [len (v3-length v)]
    (if (< len 1.0e-12) v (v3-scale v (/ 1.0 len)))))

(def v3-zero [0.0 0.0 0.0])
(def v3-x [1.0 0.0 0.0])
(def v3-y [0.0 1.0 0.0])
(def v3-z [0.0 0.0 1.0])

;; ── quaternion (x y z w) ─────────────────────────────────────────────────

(def quat-identity [0.0 0.0 0.0 1.0])

(defn quat-from-axis-angle
  "Unit quaternion for a rotation of `angle` radians about `axis` (need not
  be pre-normalised). Mirrors `glam::Quat::from_axis_angle`."
  [axis angle]
  (let [[ax ay az] (v3-normalize axis)
        half (/ angle 2.0)
        s (Math/sin half)]
    [(* ax s) (* ay s) (* az s) (Math/cos half)]))

(defn quat-from-rotation-x [angle] (quat-from-axis-angle v3-x angle))
(defn quat-from-rotation-y [angle] (quat-from-axis-angle v3-y angle))
(defn quat-from-rotation-z [angle] (quat-from-axis-angle v3-z angle))

(defn quat-normalize [[x y z w]]
  (let [len (Math/sqrt (+ (* x x) (* y y) (* z z) (* w w)))]
    (if (< len 1.0e-12)
      quat-identity
      [(/ x len) (/ y len) (/ z len) (/ w len)])))

(defn quat-from-rotation-arc
  "The shortest-arc unit quaternion rotating unit vector `from` onto unit
  vector `to`. Mirrors `glam::Quat::from_rotation_arc`, used by the
  original `segment_box` to align a link's local +Z with its segment
  direction."
  [from to]
  (let [from (v3-normalize from)
        to (v3-normalize to)
        d (v3-dot from to)]
    (cond
      (> d 0.999999) quat-identity
      (< d -0.999999)
      (let [axis (v3-normalize (if (< (Math/abs (double (first from))) 0.9)
                                  (v3-cross from v3-x)
                                  (v3-cross from v3-y)))]
        (quat-from-axis-angle axis Math/PI))
      :else
      (let [axis (v3-cross from to)
            w (+ d 1.0)]
        (quat-normalize (conj axis w))))))

(defn quat-rotate-vec3
  "Rotate 3-vector `v` by unit quaternion `q`."
  [[qx qy qz qw :as _q] v]
  (let [qv [qx qy qz]
        t (v3-scale (v3-cross qv v) 2.0)]
    (v3+ v (v3+ (v3-scale t qw) (v3-cross qv t)))))

;; ── transform (scale, rotation, translation) ────────────────────────────

(defn transform
  "A part transform, matching `Mat4::from_scale_rotation_translation`'s
  three components kept unflattened."
  ([translate] (transform v3-zero quat-identity translate))
  ([scale rotation translate]
   {:scale scale :rotation rotation :translate translate}))

(defn transform-point
  "Apply a `transform` to a local-space point `p`: `translate + rotate(scale
  .* p)` — the same composition `Mat4::from_scale_rotation_translation`
  encodes (M = T * R * S)."
  [{:keys [scale rotation translate]} p]
  (v3+ translate (quat-rotate-vec3 rotation (v3-hadamard scale p))))

(defn segment-box
  "Local box transform for a link segment `seg` (body frame): a beam from
  the origin to `seg`, local +Z = length, so a unit box scaled by this
  transform spans the segment. 1:1 port of the original `segment_box`."
  [seg thick]
  (let [len (max (v3-length seg) 1.0e-4)
        dir (v3-scale seg (/ 1.0 len))]
    (transform [thick thick len]
               (quat-from-rotation-arc v3-z dir)
               (v3-scale seg 0.5))))
