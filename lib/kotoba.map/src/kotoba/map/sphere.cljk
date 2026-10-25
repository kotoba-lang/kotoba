(ns kotoba.map.sphere
  "Globe / sphere vector math and procedural ring-mesh generation.

  Ported 1:1 from the free functions at the bottom of `kami-map/src/lib.rs`
  (Rust, kotoba-lang/kami-engine), per ADR-2607010930 (clj-wgsl migration
  Phase 4): `globe_position`, `globe_normal`, `globe_lng_lat_from_position`,
  `ray_sphere_hit`, `sphere_mesh_at`, `ring_mesh`, `ring_ribbon_mesh`,
  `spiral_ring_mesh`, `orbit_xz`. Pure vector/mesh math — no GPU calls, no
  I/O. `glam::Vec3` is represented here as a plain `[x y z]` vector of
  doubles; mesh output is `{:vertices [...] :indices [...]}` (flat
  `pos(3)+normal(3)+uv(2)` float vectors and uint index vectors, matching
  the Rust `(Vec<f32>, Vec<u32>)` tuple shape)."
  (:require [kotoba.map.constants :as k]
            [kotoba.map.projection :as proj]))

;; ---------------------------------------------------------------------------
;; Tiny Vec3 helpers
;; ---------------------------------------------------------------------------

(defn v+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn v- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn v*s [[x y z] s] [(* x s) (* y s) (* z s)])
(defn v-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn v-cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by))
   (- (* az bx) (* ax bz))
   (- (* ax by) (* ay bx))])
(defn v-length-squared [v] (v-dot v v))
(defn v-length [v] (Math/sqrt (v-length-squared v)))
(defn v-normalize-or-zero
  "Normalize `v`, returning `[0 0 0]` if its length is ~zero (mirrors glam's
  `normalize_or_zero`)."
  [v]
  (let [len (v-length v)]
    (if (< len 1e-10) [0.0 0.0 0.0] (v*s v (/ 1.0 len)))))

;; ---------------------------------------------------------------------------
;; Globe position / normal / unprojection
;; ---------------------------------------------------------------------------

(defn globe-position
  "3D position on a sphere of `radius` for geographic `[lng lat]` (degrees).
  +Y is up; matches the Rust source's axis convention (equator at y=0,
  prime meridian/equator crossing at -Z)."
  [lng lat radius]
  (let [lng-rad (k/to-radians (double lng))
        lat-rad (k/to-radians (double lat))
        cos-lat (Math/cos lat-rad)
        sin-lat (Math/sin lat-rad)
        sin-lng (Math/sin lng-rad)
        cos-lng (Math/cos lng-rad)]
    [(* radius cos-lat sin-lng)
     (* radius sin-lat)
     (- (* radius cos-lat cos-lng))]))

(defn globe-normal
  "Unit outward normal at geographic `[lng lat]` on the globe."
  [lng lat]
  (v-normalize-or-zero (globe-position lng lat 1.0)))

(defn globe-lng-lat-from-position
  "Inverse of `globe-position` (unit-sphere direction -> `[lng lat]`
  degrees, latitude clamped via `kotoba.map.projection/clamp-lat`)."
  [position]
  (let [[nx ny nz] (v-normalize-or-zero position)
        lat (k/to-degrees (Math/asin ny))
        lng (k/to-degrees (Math/atan2 nx (- nz)))]
    [lng (proj/clamp-lat lat)]))

(defn ray-sphere-hit
  "First (nearest, non-negative-t) intersection of ray `origin + t*dir` with
  a sphere of `radius` centered at the origin. Returns the hit position or
  nil."
  [origin dir radius]
  (let [a (v-dot dir dir)
        b (* 2.0 (v-dot origin dir))
        c (- (v-dot origin origin) (* radius radius))
        disc (- (* b b) (* 4.0 a c))]
    (when (>= disc 0.0)
      (let [sqrt-disc (Math/sqrt disc)
            t0 (/ (- (- b) sqrt-disc) (* 2.0 a))
            t1 (/ (+ (- b) sqrt-disc) (* 2.0 a))
            t (if (>= t0 0.0) t0 t1)]
        (when (>= t 0.0)
          (v+ origin (v*s dir t)))))))

;; ---------------------------------------------------------------------------
;; Procedural meshes — pos(3)+normal(3)+uv(2) vertex layout, matching the
;; Rust source's flat f32 vertex buffer shape.
;; ---------------------------------------------------------------------------

(defn sphere-mesh-at
  "UV-sphere mesh centered at `center` with `radius`, `stacks` latitude
  bands and `slices` longitude segments."
  [center radius stacks slices]
  (let [[cx cy cz] center
        pi Math/PI
        tau (* 2.0 Math/PI)
        vertices
        (vec
         (mapcat
          (fn [i]
            (let [phi (/ (* pi i) stacks)
                  y (Math/cos phi)
                  rr (Math/sin phi)]
              (mapcat
               (fn [j]
                 (let [theta (/ (* tau j) slices)
                       x (* rr (Math/cos theta))
                       z (* rr (Math/sin theta))]
                   [(+ cx (* x radius)) (+ cy (* y radius)) (+ cz (* z radius))
                    x y z
                    (/ (double j) slices) (/ (double i) stacks)]))
               (range (inc slices)))))
          (range (inc stacks))))
        ring (inc slices)
        indices
        (vec
         (mapcat
          (fn [i]
            (mapcat
             (fn [j]
               (let [a (+ (* i ring) j)
                     b (+ a ring)]
                 [a b (inc a) (inc a) b (inc b)]))
             (range slices)))
          (range stacks)))]
    {:vertices vertices :indices indices}))

(defn ring-mesh
  "Flat ring (annulus outline as a ribbon) mesh centered at `center`, at
  `radius`, `width` wide, with `segments` around the circle."
  [center radius width segments]
  (let [tau (* 2.0 Math/PI)
        half (* width 0.5)
        vertices
        (vec
         (mapcat
          (fn [i]
            (let [t (/ (double i) segments)
                  ang (* t tau)
                  dir [(Math/cos ang) 0.0 (Math/sin ang)]
                  tangent [(- (Math/sin ang)) 0.0 (Math/cos ang)]
                  left (v+ (v+ center (v*s dir radius)) (v*s tangent half))
                  right (v- (v+ center (v*s dir radius)) (v*s tangent half))]
              (into (into left [0.0 1.0 0.0 t 0.0])
                    (into right [0.0 1.0 0.0 t 1.0]))))
          (range (inc segments))))
        indices
        (vec
         (mapcat
          (fn [i]
            (let [base (* i 2)]
              [base (inc base) (+ base 3) base (+ base 3) (+ base 2)]))
          (range segments)))]
    {:vertices vertices :indices indices}))

(defn ring-ribbon-mesh
  "Elliptical ribbon (e.g. Saturn-style ring / orbit ribbon) around
  `center`, sized/oriented toward `focus`, tilted by `tilt` (a `[x y z]`
  direction, scaled by `globe-radius * 0.09`)."
  [center focus segments width tilt]
  (let [tau (* 2.0 Math/PI)
        half (* width 0.5)
        delta (v- focus center)
        radius-x (max 1.0 (v-length delta))
        radius-z (* radius-x 0.55)
        tilt-v (v*s (v-normalize-or-zero tilt) (* k/globe-radius 0.09))
        [_ tilt-y _] tilt-v
        vertices
        (vec
         (mapcat
          (fn [i]
            (let [t (/ (double i) segments)
                  ang (* t tau)
                  pos (v+ (v+ center [(* radius-x (Math/cos ang)) 0.0 (* radius-z (Math/sin ang))])
                          (v*s tilt-v (* (Math/sin ang) 0.4)))
                  tangent (v-normalize-or-zero
                           [(- (* radius-x (Math/sin ang)))
                            (* tilt-y 0.4 (Math/cos ang))
                            (* radius-z (Math/cos ang))])
                  side (v-normalize-or-zero (v-cross tangent [0.0 1.0 0.0]))
                  left (v+ pos (v*s side half))
                  right (v- pos (v*s side half))]
              (into (into left [0.0 1.0 0.0 t 0.0])
                    (into right [0.0 1.0 0.0 t 1.0]))))
          (range (inc segments))))
        indices
        (vec
         (mapcat
          (fn [i]
            (let [base (* i 2)]
              [base (inc base) (+ base 3) base (+ base 3) (+ base 2)]))
          (range segments)))]
    {:vertices vertices :indices indices}))

(defn spiral-ring-mesh
  "Logarithmic-ish spiral ribbon (e.g. galaxy arm) around `center`."
  [center radius width turns phase]
  (let [segments 280
        tau (* 2.0 Math/PI)
        half (* width 0.5)
        vertices
        (vec
         (mapcat
          (fn [i]
            (let [t (/ (double i) segments)
                  ang (+ phase (* t tau turns))
                  local-r (* radius (+ 0.28 (* 0.72 t)))
                  pos (v+ center [(* local-r (Math/cos ang))
                                  (* (- t 0.5) k/globe-radius 0.16)
                                  (* local-r 0.55 (Math/sin ang))])
                  tangent (v-normalize-or-zero
                           [(+ (- (* local-r (Math/sin ang))) (* radius 0.72 (Math/cos ang)))
                            (* k/globe-radius 0.16)
                            (+ (* local-r 0.55 (Math/cos ang)) (* radius 0.4 (Math/sin ang)))])
                  side (v-normalize-or-zero (v-cross tangent [0.0 1.0 0.0]))
                  left (v+ pos (v*s side half))
                  right (v- pos (v*s side half))]
              (into (into left [0.0 1.0 0.0 t 0.0])
                    (into right [0.0 1.0 0.0 t 1.0]))))
          (range (inc segments))))
        indices
        (vec
         (mapcat
          (fn [i]
            (let [base (* i 2)]
              [base (inc base) (+ base 3) base (+ base 3) (+ base 2)]))
          (range segments)))]
    {:vertices vertices :indices indices}))

(defn orbit-xz
  "Point at `radius` on the XZ-plane circle at angle `phase` (radians)."
  [radius phase]
  [(* radius (Math/cos phase)) 0.0 (* radius (Math/sin phase))])
