(ns autodrive.sensor-sim
  "Portable lidar/camera simulation surface.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  The original crate depended on `kami-sensor-sim` for lidar ring-sweep
  raycasting and pinhole-camera depth rendering. That crate is not itself a
  hardware driver — it is a pure-software simulator (ray/primitive
  intersection, pinhole projection), Isaac-Sim-API compatible — so its
  relevant surface is genuinely portable and is reimplemented here in plain
  CLJC rather than excluded:

  - a minimal `Scene` of spheres/AABBs plus ray/primitive intersection, used
    both by `autodrive.fleet`'s inter-agent ring-sweep (this is REAL src
    logic, not test scaffolding — `fleet.rs`'s `ring_sweep` performed this
    raycasting itself) and by the integration test suite to synthesize lidar
    sweeps and camera depth images against a scene;
  - a pinhole `Camera` (intrinsics + look-at + world-point depth rendering)
    mirroring the subset of `kami-sensor-sim::Camera` that
    `autodrive.perception`'s camera-depth ingestion consumes.

  This is a deliberately minimal reimplementation of the necessary surface,
  not a port of the full `kami-sensor-sim` crate."
  (:require [autodrive.geom :as g]))

;; ─────────────────────────────── Scene ───────────────────────────────

(defn scene [] [])

(defn sphere [center radius] {:type :sphere :center center :radius radius})
(defn aabb [mn mx] {:type :aabb :min mn :max mx})

(defn scene-add [scn prim] (conj scn prim))

(defn- ray-sphere
  "Nearest positive `t` where `origin + t*dir` (dir unit) hits `sphere`, or nil."
  [origin dir sph]
  (let [oc (g/sub3 origin (:center sph))
        b (g/dot3 oc dir)
        c (- (g/dot3 oc oc) (* (:radius sph) (:radius sph)))
        disc (- (* b b) c)]
    (when (>= disc 0.0)
      (let [sq (Math/sqrt disc)
            t1 (- (- b) sq)
            t2 (+ (- b) sq)
            t (cond (> t1 1e-4) t1 (> t2 1e-4) t2 :else nil)]
        t))))

(defn- ray-aabb
  "Nearest positive `t` where `origin + t*dir` hits `box`, or nil (slab method)."
  [origin dir box]
  (letfn [(slab [o d mn mx]
            (if (< (Math/abs d) 1e-9)
              (if (or (< o mn) (> o mx)) [##Inf ##-Inf] [##-Inf ##Inf])
              (let [t1 (/ (- mn o) d) t2 (/ (- mx o) d)]
                (if (< t1 t2) [t1 t2] [t2 t1]))))]
    (let [[tx0 tx1] (slab (:x origin) (:x dir) (:x (:min box)) (:x (:max box)))
          [ty0 ty1] (slab (:y origin) (:y dir) (:y (:min box)) (:y (:max box)))
          [tz0 tz1] (slab (:z origin) (:z dir) (:z (:min box)) (:z (:max box)))
          tmin (max tx0 ty0 tz0)
          tmax (min tx1 ty1 tz1)]
      (when (and (<= tmin tmax) (> tmax 1e-4))
        (if (> tmin 1e-4) tmin tmax)))))

(defn- ray-prim [origin dir prim]
  (case (:type prim)
    :sphere (ray-sphere origin dir prim)
    :aabb (ray-aabb origin dir prim)))

(defn cast-ray
  "Nearest hit `{:t :prim-index}` of `dir` (unit) from `origin` against `scn`
  within `[range-min range-max]`, or nil."
  [scn origin dir range-min range-max]
  (loop [i 0 prims (seq scn) best nil]
    (if (nil? prims)
      best
      (let [t (ray-prim origin dir (first prims))
            best' (if (and t (>= t range-min) (<= t range-max)
                           (or (nil? best) (< t (:t best))))
                    {:t t :prim-index i}
                    best)]
        (recur (inc i) (next prims) best')))))

;; ─────────────────────────────── Lidar ───────────────────────────────

(defn lidar-intrinsics
  [& {:keys [hfov vfov h-beams v-beams range-min range-max]
      :or {vfov 0.05 v-beams 1}}]
  {:hfov hfov :vfov vfov :h-beams h-beams :v-beams v-beams
   :range-min range-min :range-max range-max})

(defn ring-sweep
  "Sweep a planar ring lidar mounted at `mount-z` above `pose` (a `Pose2`,
  i.e. `{:x :y :yaw}`) against `scn`. Returns a vector of lidar returns
  `{:range :point-sensor :prim-index}`, `:point-sensor` in the sensor frame
  (+x forward, +y left, +z up, relative to the mount). One entry per beam;
  a miss has `:range ##Inf` and `:prim-index -1` (mirrors the original
  crate's `LidarReturn`, whose non-finite `range` marks a no-return beam)."
  [intr pose mount-z scn]
  (let [{:keys [hfov h-beams range-min range-max]} intr
        origin (g/v3 (:x pose) (:y pose) mount-z)
        yaw (:yaw pose)]
    (mapv
     (fn [i]
       (let [local-ang (+ (- (/ hfov 2.0)) (* hfov (/ (+ i 0.5) h-beams)))
             world-ang (+ yaw local-ang)
             dir (g/v3 (Math/cos world-ang) (Math/sin world-ang) 0.0)
             hit (cast-ray scn origin dir range-min range-max)]
         (if hit
           (let [world-hit (g/add3 origin (g/scale3 dir (:t hit)))
                 rel (g/sub3 world-hit origin)
                 s (Math/sin yaw) c (Math/cos yaw)
                 lx (+ (* c (:x rel)) (* s (:y rel)))
                 ly (+ (* (- s) (:x rel)) (* c (:y rel)))]
             {:range (:t hit)
              :point-sensor (g/v3 lx ly (:z rel))
              :prim-index (:prim-index hit)})
           {:range ##Inf :point-sensor (g/v3 0.0 0.0 0.0) :prim-index -1})))
     (range h-beams))))

;; ─────────────────────────────── Camera ───────────────────────────────

(defn camera-intrinsics-from-hfov
  "Pinhole intrinsics from image `width`/`height` and horizontal FOV (rad),
  square pixels."
  [width height hfov]
  (let [fx (/ width (* 2.0 (Math/tan (/ hfov 2.0))))]
    {:width width :height height :fx fx :fy fx :cx (/ width 2.0) :cy (/ height 2.0)}))

(defn camera
  [name path intrinsics]
  {:name name :path path :intrinsics intrinsics
   :eye (g/v3 0.0 0.0 0.0) :right (g/v3 0.0 -1.0 0.0)
   :down (g/v3 0.0 0.0 -1.0) :forward (g/v3 1.0 0.0 0.0)})

(defn look-at
  "Orient `cam` at `eye` looking toward `target`, with world-up `up`. Camera
  frame: +x right, +y down, +z forward."
  [cam eye target up]
  (let [fwd (g/normalize3 (g/sub3 target eye))
        right (g/normalize3 (g/cross3 fwd up))
        down (g/cross3 fwd right)]
    (assoc cam :eye eye :right right :down down :forward fwd)))

(defn- world->cam
  "World point `p` in `cam`'s frame: `{:x :y :z}` (x right, y down, z forward)."
  [cam p]
  (let [rel (g/sub3 p (:eye cam))]
    (g/v3 (g/dot3 rel (:right cam)) (g/dot3 rel (:down cam)) (g/dot3 rel (:forward cam)))))

(defn cam->world
  "Camera-frame point `p` (x right, y down, z forward) back into world coords."
  [cam p]
  (g/add3 (:eye cam)
          (g/add3 (g/scale3 (:right cam) (:x p))
                  (g/add3 (g/scale3 (:down cam) (:y p))
                          (g/scale3 (:forward cam) (:z p))))))

(defn render-points-to-depth-image
  "Render world `pts` (a seq of Vec3) through `cam`'s pinhole intrinsics into
  a depth image `{:width :height :pixels}`, `:pixels` a vector of length
  `width*height`, row-major (`v*width+u`); each entry is the nearest camera
  depth (`z` forward) hitting that pixel, or `##Inf` for an empty pixel."
  [cam pts]
  (let [{:keys [width height fx fy cx cy]} (:intrinsics cam)
        n (* width height)
        pixels (atom (vec (repeat n ##Inf)))]
    (doseq [p pts]
      (let [c (world->cam cam p)
            z (:z c)]
        (when (> z 1e-6)
          (let [u (long (Math/floor (+ (/ (* (:x c) fx) z) cx)))
                v (long (Math/floor (+ (/ (* (:y c) fy) z) cy)))]
            (when (and (>= u 0) (< u width) (>= v 0) (< v height))
              (let [idx (+ (* v width) u)]
                (swap! pixels update idx #(min % z))))))))
    {:width width :height height :pixels @pixels}))

(defn populated-count
  "Number of finite (occupied) pixels in a depth image."
  [depth]
  (count (filter g/finite? (:pixels depth))))
