(ns cam.look-constraint
  "Look-at constraint: orient a camera to face a target point, with an
  optional up-vector reference and roll-lock behaviour (the returned basis
  always has zero roll around the forward axis relative to `up`, since
  `up` is re-derived from `right`/`forward` rather than used verbatim —
  that re-derivation *is* the roll lock: the camera never banks on its
  own, it only banks if the caller feeds it a rotated `up`).

  New camera-rig implementation, not a port of anything — see the root
  `cam` namespace docstring. Pure 3-vector math + a rotation-matrix-to-
  quaternion conversion, no external dependency.")

;; ---------------------------------------------------------------------
;; Minimal private vec3 helpers.
;; ---------------------------------------------------------------------

(defn- sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn- cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn- sqrt* [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(defn- abs* [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))
(defn- vlen [v] (sqrt* (dot v v)))
(defn- normalize
  "Unit vector in the direction of `v`. Returns `v` unchanged if it is
  (numerically) the zero vector, since there is no sensible direction to
  report and callers here always guard the degenerate cases before
  calling this."
  [v]
  (let [l (vlen v)]
    (if (< l 1e-12) v (mapv #(/ % l) v))))

(defn- fallback-up-for
  "A reference vector guaranteed not to be (nearly) parallel to `forward`,
  used when the caller-supplied `up` *is* nearly parallel to `forward`
  (e.g. looking straight up with a `[0 1 0]` up-vector). World `+Y` is
  tried first since that is the overwhelmingly common `up`; if `forward`
  is itself close to `+Y` (the actual degenerate case), world `+X` is
  used instead."
  [forward]
  (let [candidate [0.0 1.0 0.0]]
    (if (> (abs* (dot forward candidate)) 0.999)
      [1.0 0.0 0.0]
      candidate)))

(defn look-at
  "Build an orthonormal camera basis `{:forward :right :up}` (all unit
  `[x y z]` vectors) that faces `target-pos` from `eye-pos`, using `up` as
  the reference \"which way is up\" vector (typically world up, `[0 1 0]`).

  Standard forward/right/up construction:
  `forward = normalize(target - eye)`,
  `right   = normalize(cross(forward, up))`,
  `up'     = cross(right, forward)`
  (`up'` is already unit-length since `right` and `forward` are
  orthonormal — no separate normalize needed).

  Degenerate case: if `forward` is (numerically) parallel to `up` —
  looking straight along the up-vector — `cross(forward, up)` is ~zero
  and there is no unique `right`. In that case a fallback reference
  vector not parallel to `forward` is substituted for `up` before taking
  the cross product (see `fallback-up-for`), which yields a *sensible but
  otherwise arbitrary* `right`/`up'` (the roll around `forward` is
  undefined by the problem itself when `up` gives no roll information, so
  any orthonormal completion is equally valid)."
  [eye-pos target-pos up]
  (let [forward (normalize (sub target-pos eye-pos))
        up-n (normalize up)
        right-raw (cross forward up-n)
        degenerate? (< (vlen right-raw) 1e-8)
        right (if degenerate?
                (normalize (cross forward (fallback-up-for forward)))
                (normalize right-raw))
        up' (cross right forward)]
    {:forward forward :right right :up up'}))

(defn basis->quaternion
  "Rotation-matrix-to-quaternion conversion (Shepperd's method: branch on
  the largest of `trace` / the three diagonal terms, which stays
  numerically stable for every orientation — the naive \"trace-only\"
  formula divides by ~0 near a 180-degree rotation).

  `basis` is as returned by `look-at`: an orthonormal `{:forward :right
  :up}` triple, interpreted as the camera's local axes expressed in world
  space using the common OpenGL/glTF camera convention — local `+X` =
  `right`, local `+Y` = `up`, local `-Z` = `forward` (the camera looks
  down its own `-Z`). Returns `[w x y z]`.

  Hand-verified test cases (see `cam.look-constraint-test`):
  - `(look-at [0 0 0] [0 0 -1] [0 1 0])` — looking down world `-Z` with
    `+Y` up, i.e. the camera's local axes coincide with world axes — is
    the identity rotation `[1 0 0 0]`.
  - `(look-at [0 0 0] [1 0 0] [0 1 0])` — looking down world `+X` — is a
    90-degree rotation about `-Y`, `[0.70710678 0 -0.70710678 0]`.
    (Sanity check for that value: rotating the local forward axis
    `[0 0 -1]` by this quaternion must land on `[1 0 0]`, the actual look
    direction; working through the quaternion-rotation formula by hand
    confirms it does.)"
  [{:keys [forward right up]}]
  (let [[rx ry rz] right
        [ux uy uz] up
        [fx fy fz] forward
        m00 rx, m01 ux, m02 (- fx)
        m10 ry, m11 uy, m12 (- fy)
        m20 rz, m21 uz, m22 (- fz)
        trace (+ m00 m11 m22)]
    (cond
      (pos? trace)
      (let [s (* 2.0 (sqrt* (+ trace 1.0)))]
        [(/ s 4.0) (/ (- m21 m12) s) (/ (- m02 m20) s) (/ (- m10 m01) s)])

      (and (> m00 m11) (> m00 m22))
      (let [s (* 2.0 (sqrt* (+ 1.0 m00 (- m11) (- m22))))]
        [(/ (- m21 m12) s) (/ s 4.0) (/ (+ m01 m10) s) (/ (+ m02 m20) s)])

      (> m11 m22)
      (let [s (* 2.0 (sqrt* (+ 1.0 m11 (- m00) (- m22))))]
        [(/ (- m02 m20) s) (/ (+ m01 m10) s) (/ s 4.0) (/ (+ m12 m21) s)])

      :else
      (let [s (* 2.0 (sqrt* (+ 1.0 m22 (- m00) (- m11))))]
        [(/ (- m10 m01) s) (/ (+ m02 m20) s) (/ (+ m12 m21) s) (/ s 4.0)]))))
