(ns character.math
  "Minimal Vec3/Quat/Mat4 math, matching glam's conventions (right-handed,
  column-major Mat4, quaternion stored `[x y z w]`) — the same conventions
  established in the sibling restoration `kotoba-lang/skeleton`'s
  `skeleton/math.cljc`, reimplemented locally here so this repo stays
  zero-dep (no hard cross-repo dependency). Restored as part of the
  kami-character port (kami-engine, deleted PR #82), ADR-2607010930,
  com-junkawasaki/root.

  Vec3 = `[x y z]`. Quat = `[x y z w]`. Mat4 = 16-element vector,
  column-major (`m[12] m[13] m[14]` = translation), matching glam's
  `to_cols_array`.")

;; ── Platform math (JVM `Math/` vs JS `js/Math`) ──

(defn sqrt [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(defn sin [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))
(defn cos [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))
(defn acos [x] #?(:clj (Math/acos x) :cljs (js/Math.acos x)))
;; Java's Math/signum has no JS equivalent by that name (Math.signum is not a
;; function in browsers/Node — only Math.sign is); a bare `(Math/signum x)`
;; compiles in cljs to a literal, nonexistent `Math.signum(x)` call and throws
;; at runtime. `Math/signum` also differs from `Math/sign` for `-0.0`/`NaN`
;; (returns `-0.0`/`NaN` unchanged rather than `0`) but callers here (blendshape
;; width offsets) only ever pass ordinary finite face-mesh coordinates, so the
;; distinction doesn't matter in practice.
(defn signum [x] #?(:clj (Math/signum (double x)) :cljs (js/Math.sign x)))
(def pi #?(:clj Math/PI :cljs js/Math.PI))

;; ── Vec3 ──────────────────────────────────────

(def vec3-zero [0.0 0.0 0.0])
(def vec3-one [1.0 1.0 1.0])

(defn vec3+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn vec3- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn vec3-scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn vec3-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn vec3-cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn vec3-length-squared [v] (vec3-dot v v))
(defn vec3-length [v] (sqrt (vec3-length-squared v)))
(defn vec3-normalize-or-zero [v]
  (let [l (vec3-length v)]
    (if (zero? l) vec3-zero (vec3-scale v (/ 1.0 l)))))
(defn vec3-normalize [v] (vec3-normalize-or-zero v))

;; ── Quat (`[x y z w]`) ───────────────────────────

(def quat-identity [0.0 0.0 0.0 1.0])

(defn quat-mul
  "Hamilton product; `(quat-mul a b)` composes as glam's `a * b` (apply
  `b`'s rotation, then `a`'s)."
  [[x1 y1 z1 w1] [x2 y2 z2 w2]]
  [(+ (* w1 x2) (* x1 w2) (* y1 z2) (- (* z1 y2)))
   (+ (- (* w1 y2) (* x1 z2)) (* y1 w2) (* z1 x2))
   (+ (* w1 z2) (* x1 y2) (- (* y1 x2)) (* z1 w2))
   (- (* w1 w2) (* x1 x2) (* y1 y2) (* z1 z2))])

(defn quat-dot [[x1 y1 z1 w1] [x2 y2 z2 w2]] (+ (* x1 x2) (* y1 y2) (* z1 z2) (* w1 w2)))
(defn quat-length-squared [q] (quat-dot q q))
(defn quat-normalize
  [q]
  (let [l (sqrt (quat-length-squared q))]
    (if (zero? l) quat-identity (mapv #(/ % l) q))))

(defn quat-from-axis-angle
  "Rotation quaternion for `angle` radians around unit `axis`."
  [axis angle]
  (let [h (/ angle 2.0)
        s (sin h)]
    (quat-normalize (conj (vec3-scale axis s) (cos h)))))

(defn quat-from-euler-xyz
  "Rotation quaternion from Euler angles (radians), applied in X then Y
  then Z order (matches glam's `EulerRot::XYZ`: `q = qz * qy * qx`)."
  [rx ry rz]
  (let [qx (quat-from-axis-angle [1.0 0.0 0.0] rx)
        qy (quat-from-axis-angle [0.0 1.0 0.0] ry)
        qz (quat-from-axis-angle [0.0 0.0 1.0] rz)]
    (quat-mul qz (quat-mul qy qx))))

;; ── Mat4 (column-major 16-vector) ────────────────

(def mat4-identity
  [1.0 0.0 0.0 0.0
   0.0 1.0 0.0 0.0
   0.0 0.0 1.0 0.0
   0.0 0.0 0.0 1.0])

(defn mat4-mul
  "`(mat4-mul a b)` = glam's `a * b` (column-major, applies `b` first)."
  [a b]
  (let [ai (fn [col row] (nth a (+ (* col 4) row)))
        bi (fn [col row] (nth b (+ (* col 4) row)))]
    (vec
     (for [col (range 4) row (range 4)]
       (reduce + (for [k (range 4)] (* (ai k row) (bi col k))))))))

(defn quat-to-mat3-cols
  "Rotation quaternion -> 3 columns of 3 (9 values), each column a Vec3."
  [[x y z w]]
  (let [x2 (+ x x) y2 (+ y y) z2 (+ z z)
        xx (* x x2) xy (* x y2) xz (* x z2)
        yy (* y y2) yz (* y z2) zz (* z z2)
        wx (* w x2) wy (* w y2) wz (* w z2)]
    [[(- 1.0 (+ yy zz)) (+ xy wz) (- xz wy)]
     [(- xy wz) (- 1.0 (+ xx zz)) (+ yz wx)]
     [(+ xz wy) (- yz wx) (- 1.0 (+ xx yy))]]))

(defn mat4-from-scale-rotation-translation
  [[sx sy sz] q [tx ty tz]]
  (let [[c0 c1 c2] (quat-to-mat3-cols q)
        [c0 c1 c2] [(vec3-scale c0 sx) (vec3-scale c1 sy) (vec3-scale c2 sz)]]
    (vec (concat c0 [0.0] c1 [0.0] c2 [0.0] [tx ty tz 1.0]))))

(defn mat4-to-cols-array-2d
  [m]
  [(vec (subvec m 0 4)) (vec (subvec m 4 8)) (vec (subvec m 8 12)) (vec (subvec m 12 16))])

(defn mat4-from-cols-array-2d [cols] (vec (apply concat cols)))

;; ── Misc scalar helpers ───────────────────────────

(defn clamp [x lo hi] (max lo (min hi x)))
(defn to-radians [deg] (* deg (/ pi 180.0)))

;; ── Deterministic hash (shared across hair/hair-gen/metahuman) ────
;; u32 hash constants, expressed as their two's-complement int32
;; equivalents (2654435761 = 0x9E3779B1, 2246822519 = 0x85EBCA77,
;; 0x85ebca6b) since Rust's `wrapping_mul` on u32 matches JVM `int`
;; wraparound bit-for-bit.

(def ^:private hash-k1 (int -1640531535))
(def ^:private hash-k2 (int -2048144777))
(def ^:private hash-k3 (int -2048144789))

(defn hash-f32
  "Simple deterministic hash for pseudo-random variation, matching the
  Rust crate's `hash_f32(a: u32, b: u32) -> f32` used across
  hair/hair-gen/metahuman modules."
  [a b]
  (let [h (unchecked-add (unchecked-multiply (int a) hash-k1) (unchecked-multiply (int b) hash-k2))
        h (bit-xor h (unsigned-bit-shift-right h 16))
        h (unchecked-multiply h hash-k3)
        h (bit-xor h (unsigned-bit-shift-right h 13))]
    (/ (double (bit-and h 0xFFFF)) 65535.0)))

(defn hash-u32-x
  "Deterministic per-vertex-index hash used by `apply-asymmetry` /
  `apply-wrinkle-displacement` in metahuman.rs: `(i.wrapping_mul(k) >>
  16) as f32 / 65535.0`."
  [i k]
  (let [h (unchecked-multiply (int i) (int k))]
    (/ (double (bit-and (unsigned-bit-shift-right h 16) 0xFFFF)) 65535.0)))
