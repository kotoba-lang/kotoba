(ns kotoba.webgpu-rs.mat4
  "Minimal column-major 4x4 matrix math — the cljc equivalent of the
  handful of `glam::Mat4` operations kami-webgpu-rs actually called
  (`from_translation`, `from_rotation_y`, `from_scale`, `*` (compose),
  `perspective_rh`, `look_at_rh`, `orthographic_rh`, `transform_point3`,
  `to_cols_array`). Not a general-purpose linear-algebra library — only
  what the renderer's pure per-frame camera/transform math needs.

  A matrix is a flat vector of 16 doubles in column-major order (columns
  `[c0 c1 c2 c3]`, each 4 elements), matching `glam::Mat4::to_cols_array`
  and the `mat4x4<f32>` WGSL uniform layout kami-webgpu-rs's shaders
  expect — no translation needed at the uniform-buffer boundary.

  No network, no I/O.")

(def identity-mat
  [1.0 0.0 0.0 0.0
   0.0 1.0 0.0 0.0
   0.0 0.0 1.0 0.0
   0.0 0.0 0.0 1.0])

(defn from-translation [[x y z]]
  [1.0 0.0 0.0 0.0
   0.0 1.0 0.0 0.0
   0.0 0.0 1.0 0.0
   x   y   z   1.0])

(defn from-scale [[x y z]]
  [x   0.0 0.0 0.0
   0.0 y   0.0 0.0
   0.0 0.0 z   0.0
   0.0 0.0 0.0 1.0])

(defn from-rotation-y
  "Right-handed rotation about +Y by `angle` radians."
  [angle]
  (let [c (Math/cos angle) s (Math/sin angle)]
    [c   0.0 (- s) 0.0
     0.0 1.0 0.0   0.0
     s   0.0 c     0.0
     0.0 0.0 0.0   1.0]))

(defn mul
  "Matrix product `a * b` (column-major, same semantics as `glam`'s `*`:
  applying the result to a point applies `b` first, then `a`)."
  [a b]
  (let [col (fn [m i] [(nth m (* i 4)) (nth m (+ (* i 4) 1))
                        (nth m (+ (* i 4) 2)) (nth m (+ (* i 4) 3))])
        row (fn [m i] [(nth m i) (nth m (+ i 4)) (nth m (+ i 8)) (nth m (+ i 12))])
        dot4 (fn [[x1 y1 z1 w1] [x2 y2 z2 w2]] (+ (* x1 x2) (* y1 y2) (* z1 z2) (* w1 w2)))]
    (vec (for [c (range 4) r (range 4)]
           (dot4 (row a r) (col b c))))))

(defn mul* [& ms] (reduce mul ms))

(defn transform-point3
  "`m` applied to point `p` (implicit `w=1`), returning `[x y z]` after
  the perspective divide — mirrors `glam::Mat4::transform_point3`."
  [m [px py pz]]
  (let [x (+ (* (nth m 0) px) (* (nth m 4) py) (* (nth m 8) pz) (nth m 12))
        y (+ (* (nth m 1) px) (* (nth m 5) py) (* (nth m 9) pz) (nth m 13))
        z (+ (* (nth m 2) px) (* (nth m 6) py) (* (nth m 10) pz) (nth m 14))
        w (+ (* (nth m 3) px) (* (nth m 7) py) (* (nth m 11) pz) (nth m 15))
        w (if (zero? w) 1.0 w)]
    [(/ x w) (/ y w) (/ z w)]))

;; --- camera matrices (glam::Mat4::{perspective_rh,look_at_rh,orthographic_rh}) ---

(defn perspective-rh
  "Right-handed perspective projection, `0..1` (WebGPU/wgpu) depth range —
  `glam::Mat4::perspective_rh`. `fov-y-radians` is vertical FOV."
  [fov-y-radians aspect z-near z-far]
  (let [f (/ 1.0 (Math/tan (/ fov-y-radians 2.0)))
        r (/ z-far (- z-near z-far))]
    [(/ f aspect) 0.0 0.0 0.0
     0.0 f 0.0 0.0
     0.0 0.0 r -1.0
     0.0 0.0 (* r z-near) 0.0]))

(defn orthographic-rh
  "Right-handed orthographic projection, `0..1` depth range —
  `glam::Mat4::orthographic_rh`."
  [left right bottom top z-near z-far]
  (let [sx (/ 2.0 (- right left))
        sy (/ 2.0 (- top bottom))
        sz (/ 1.0 (- z-near z-far))
        tx (/ (+ right left) (- left right))
        ty (/ (+ top bottom) (- bottom top))
        tz (* sz z-near)]
    [sx 0.0 0.0 0.0
     0.0 sy 0.0 0.0
     0.0 0.0 sz 0.0
     tx ty tz 1.0]))

(defn- v3-sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- v3-cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn- v3-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn- v3-normalize [v]
  (let [len (Math/sqrt (v3-dot v v))]
    (if (zero? len) v (mapv #(/ % len) v))))

(defn look-at-rh
  "Right-handed view matrix looking from `eye` toward `target`, `up`
  world-up — `glam::Mat4::look_at_rh`."
  [eye target up]
  (let [f (v3-normalize (v3-sub target eye))
        s (v3-normalize (v3-cross f up))
        u (v3-cross s f)]
    [(nth s 0) (nth u 0) (- (nth f 0)) 0.0
     (nth s 1) (nth u 1) (- (nth f 1)) 0.0
     (nth s 2) (nth u 2) (- (nth f 2)) 0.0
     (- (v3-dot s eye)) (- (v3-dot u eye)) (v3-dot f eye) 1.0]))
