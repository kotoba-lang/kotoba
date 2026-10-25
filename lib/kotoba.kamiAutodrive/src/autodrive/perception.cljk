(ns autodrive.perception
  "Perception: lidar returns -> 2-D occupancy grid (+ configuration-space
  inflation for planning).

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  Consumes lidar returns (`{:range :point-sensor :prim-index}`, see
  `autodrive.sensor-sim`) directly. Each finite-range beam is projected to
  the ground plane, height-filtered to drop the ground sweep and overhead
  clutter, and rasterised into an occupancy grid. The grid is then inflated
  by the vehicle footprint so the planner can treat the robot as a point.

  The grid map is plain immutable data (`{:origin :res :w :h :cells}`,
  `:cells` a Clojure vector of 0/1); every operation here is a pure function
  returning an updated grid, mirroring the original `&mut self` methods."
  (:require [autodrive.geom :as g]
            [autodrive.types :as t]
            [autodrive.sensor-sim :as sensor-sim]))

(defn centered
  "Grid spanning `[center - half-extent, center + half-extent]` on each axis."
  [center half-extent res]
  (let [n (max 1 (long (Math/ceil (/ (* 2.0 half-extent) res))))
        origin (g/sub2 center (g/splat2 (* (- n 1.0) 0.5 res)))]
    {:origin origin :res res :w n :h n :cells (vec (repeat (* n n) 0))}))

(defn clear [g] (assoc g :cells (vec (repeat (* (:w g) (:h g)) 0))))

(defn world->cell
  "World point -> `[cx cy]`, or nil if outside the grid."
  [g p]
  (let [rel (g/scale2 (g/sub2 p (:origin g)) (/ 1.0 (:res g)))
        cx (Math/round (:x rel))
        cy (Math/round (:y rel))]
    (when-not (or (< cx 0) (< cy 0) (>= cx (:w g)) (>= cy (:h g)))
      [(long cx) (long cy)])))

(defn cell->world
  "Cell -> world coordinate of its centre."
  [g x y]
  (g/add2 (:origin g) (g/scale2 (g/v2 x y) (:res g))))

(defn cell-idx [g x y] (+ (* y (:w g)) x))

(defn occupied? [g x y] (not= 0 (nth (:cells g) (cell-idx g x y))))

(defn mark-world [g p]
  (if-let [[x y] (world->cell g p)]
    (assoc-in g [:cells (cell-idx g x y)] 1)
    g))

(defn ingest-lidar
  "Ingest a lidar sweep. `sensor` is the lidar pose in the world (planar);
  `z-band` is `[lo hi]`, keeping only hits whose sensor-frame height lies in
  that range (drops the ground plane and overhead returns)."
  [g returns sensor z-band]
  (let [[lo hi] z-band]
    (reduce (fn [g r]
              (let [rng (:range r)]
                (if (or (nil? rng) (not (g/finite? rng)))
                  g
                  (let [p (:point-sensor r)]
                    (if (or (< (:z p) lo) (> (:z p) hi))
                      g
                      (mark-world g (t/to-world sensor (g/v2 (:x p) (:y p)))))))))
            g returns)))

(defn ingest-camera-depth
  "Ingest a depth image from a pinhole camera (RGB-D / stereo costmap path,
  complementary to lidar). Each finite-depth pixel is back-projected through
  the intrinsics to a camera-frame point, transformed to the world (z-up),
  height-filtered by `world-z-band` (drop ground + overhead), and rasterised
  to occupancy."
  [g depth cam world-z-band]
  (let [{:keys [width height fx fy cx cy]} (:intrinsics cam)
        [lo hi] world-z-band]
    (reduce
     (fn [g v]
       (reduce
        (fn [g u]
          (let [d (nth (:pixels depth) (+ (* v width) u))]
            (if-not (g/finite? d)
              g
              (let [x (/ (* (+ u 0.5 (- cx)) d) fx)
                    y (/ (* (+ v 0.5 (- cy)) d) fy)
                    w (sensor-sim/cam->world cam (g/v3 x y d))]
                (if (or (< (:z w) lo) (> (:z w) hi))
                  g
                  (mark-world g (g/v2 (:x w) (:y w))))))))
        g (range width)))
     g (range height))))

(defn inflated
  "Return a configuration-space copy with every occupied cell dilated by
  `radius` metres (box dilation). The planner runs on this so it can treat
  the vehicle as a point."
  [g radius]
  (let [r (long (Math/ceil (/ radius (:res g))))]
    (if (<= r 0)
      g
      (let [w (:w g) h (:h g)
            marks (for [y (range h) x (range w)
                        :when (occupied? g x y)
                        dy (range (- r) (inc r))
                        dx (range (- r) (inc r))
                        :when (<= (+ (* dx dx) (* dy dy)) (* r r))
                        :let [nx (+ x dx) ny (+ y dy)]
                        :when (and (>= nx 0) (>= ny 0) (< nx w) (< ny h))]
                    (cell-idx g nx ny))]
        (update g :cells
                (fn [cells] (reduce (fn [c i] (assoc c i 1)) cells marks)))))))

(defn to-cost-grid
  "View as a cost grid: occupied -> 0 (wall), free -> 1 (unit cost). Indexed
  `[y][x]` (vector of row vectors)."
  [g]
  (mapv (fn [y] (mapv (fn [x] (if (occupied? g x y) 0 1)) (range (:w g)))) (range (:h g))))

(defn line-clear?
  "True iff the straight segment `a..b` stays on free, in-bounds cells
  (sampled at sub-cell spacing)."
  [g a b]
  (let [len (g/distance2 a b)
        steps (max 1 (long (Math/ceil (/ len (* (:res g) 0.5)))))]
    (loop [k 0]
      (if (> k steps)
        true
        (let [p (g/lerp2 a b (/ (double k) steps))]
          (if-let [[x y] (world->cell g p)]
            (if (occupied? g x y) false (recur (inc k)))
            false))))))

(defn nearest-free
  "Nearest free cell to `p` (spiral search), as `[x y]`. Used to snap a
  start/goal that lands on (or just inside) an inflated obstacle."
  [g p]
  (when-let [[cx cy] (world->cell g p)]
    (if-not (occupied? g cx cy)
      [cx cy]
      (let [w (:w g) h (:h g) max-r (max w h)]
        (loop [r 1]
          (if (>= r max-r)
            nil
            (let [hit (first
                       (for [dy (range (- r) (inc r))
                             dx (range (- r) (inc r))
                             :when (or (= (Math/abs (int dx)) r) (= (Math/abs (int dy)) r))
                             :let [nx (+ cx dx) ny (+ cy dy)]
                             :when (and (>= nx 0) (>= ny 0) (< nx w) (< ny h)
                                        (not (occupied? g nx ny)))]
                         [nx ny]))]
              (or hit (recur (inc r))))))))))

;; ─────────────────────────── Reactive clearance ───────────────────────────

(defn forward-clearance
  "Smallest forward-cone obstacle range from a raw lidar sweep, for reactive
  emergency braking (independent of the grid/planner). Returns the nearest
  hit distance within a half-angle `cone` of straight-ahead and within
  `z-band`, or nil."
  [returns cone z-band]
  (let [[lo hi] z-band]
    (loop [rs returns nearest ##Inf]
      (if (empty? rs)
        (when (g/finite? nearest) nearest)
        (let [r (first rs)
              rng (:range r)]
          (if (or (nil? rng) (not (g/finite? rng)))
            (recur (rest rs) nearest)
            (let [p (:point-sensor r)]
              (if (or (< (:z p) lo) (> (:z p) hi))
                (recur (rest rs) nearest)
                (let [az (Math/abs (Math/atan2 (:y p) (:x p)))]
                  (if (<= az cone)
                    (let [ground-range (Math/sqrt (+ (* (:x p) (:x p)) (* (:y p) (:y p))))]
                      (recur (rest rs) (min nearest ground-range)))
                    (recur (rest rs) nearest)))))))))))

(defn forward-clearance-camera
  "Smallest forward-cone obstacle range from a depth camera, for a reactive
  emergency reflex when running camera-only (no forward lidar). Mirrors
  `forward-clearance`: returns the nearest ground-plane range within a
  half-angle `cone` of the camera's optical axis and within `world-z-band`
  (after back-projection), or nil."
  [depth cam cone world-z-band]
  (let [{:keys [width height fx fy cx cy]} (:intrinsics cam)
        [lo hi] world-z-band]
    (loop [v 0 nearest ##Inf]
      (if (>= v height)
        (when (g/finite? nearest) nearest)
        (recur (inc v)
               (loop [u 0 nearest nearest]
                 (if (>= u width)
                   nearest
                   (let [d (nth (:pixels depth) (+ (* v width) u))]
                     (if-not (g/finite? d)
                       (recur (inc u) nearest)
                       (let [x (/ (* (+ u 0.5 (- cx)) d) fx)]
                         (if (> (Math/abs (Math/atan2 x d)) cone)
                           (recur (inc u) nearest)
                           (let [y (/ (* (+ v 0.5 (- cy)) d) fy)
                                 w (sensor-sim/cam->world cam (g/v3 x y d))]
                             (if (or (< (:z w) lo) (> (:z w) hi))
                               (recur (inc u) nearest)
                               (let [ground-range (Math/sqrt (+ (* x x) (* d d)))]
                                 (recur (inc u) (min nearest ground-range))))))))))))))))
