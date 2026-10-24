(ns floorplan-lab.fusion
  "Sensor fusion: combine a dead-reckoning trajectory
  (`floorplan-lab.motion`), chirp-echo wall-distance readings
  (`floorplan-lab.sonar`), and BLE-trilaterated position corrections
  (`floorplan-lab.ble`) into a point cloud of estimated wall points, then
  a simplified room outline (convex hull). Part of the indoor
  floorplan-lab (ADR-2607140600 Phase 3a device-capability bridge) --
  SOFTWARE ONLY.

  FUSION METHOD (explicitly simple -- see README \"Future work\"):
  `correct-with-ble` is a plain weighted average of the dead-reckoning
  position and the BLE-trilaterated position (no covariance, no Kalman
  gain). A real implementation would fuse via an EKF/UKF weighting each
  source by its actual noise covariance, and would also correct HEADING
  drift (this lab's fusion only corrects x/y).")

;; ---------- portable math ----------

#?(:clj (defn- sin ^double [^double x] (Math/sin x))
   :cljs (defn- sin [x] (js/Math.sin x)))
#?(:clj (defn- cos ^double [^double x] (Math/cos x))
   :cljs (defn- cos [x] (js/Math.cos x)))

(defn correct-with-ble
  "Weighted-average fusion of a dead-reckoning POSE ({:x :y ...}) with a
  BLE-trilaterated [ble-x ble-y] position. WEIGHT in [0,1] is how much to
  trust the BLE fix (0 = ignore BLE entirely, 1 = fully replace with
  BLE) -- a crude stand-in for a real Kalman gain. Returns POSE with :x
  and :y replaced by the blend; other keys (e.g. :heading, :vx, :vy)
  pass through unchanged."
  [pose [ble-x ble-y] weight]
  (assoc pose
         :x (+ (* (- 1.0 weight) (:x pose)) (* weight ble-x))
         :y (+ (* (- 1.0 weight) (:y pose)) (* weight ble-y))))

(defn wall-point
  "The world-frame [x y] of a wall reflection: POSE's position, offset by
  DISTANCE-M along POSE's :heading (the direction the chirp was aimed --
  this lab assumes the phone points the mic/speaker at the wall being
  measured, a simplification noted in the README)."
  [pose distance-m]
  [(+ (:x pose) (* distance-m (cos (:heading pose))))
   (+ (:y pose) (* distance-m (sin (:heading pose))))])

(defn collect-wall-points
  "Given TRAJECTORY (as `floorplan-lab.motion/walk-trajectory` returns)
  and READINGS (a seq of {:sample-index :distance-m}, each naming which
  TRAJECTORY pose the chirp was fired from and the sonar-estimated
  distance at that moment), return the seq of estimated [x y] wall
  points. Readings with a nil :distance-m (sonar found no echo) or an
  out-of-range :sample-index are dropped."
  [trajectory readings]
  (let [poses (vec trajectory)]
    (vec
     (for [{:keys [sample-index distance-m]} readings
           :when (and distance-m sample-index
                      (>= sample-index 0) (< sample-index (count poses)))]
       (wall-point (poses sample-index) distance-m)))))

;; ---------- convex hull (Andrew's monotone chain) -> simplified floorplan polygon ----------

(defn- cross-2d [[ox oy] [ax ay] [bx by]]
  (- (* (- ax ox) (- by oy)) (* (- ay oy) (- bx ox))))

(defn- build-half-hull [pts]
  (reduce (fn [hull p]
            (loop [h hull]
              (if (and (>= (count h) 2)
                       (<= (cross-2d (nth h (- (count h) 2)) (peek h) p) 0))
                (recur (pop h))
                (conj h p))))
          []
          pts))

(defn convex-hull
  "Andrew's monotone-chain convex hull of POINTS (seq of [x y]). Returns
  the hull vertices in CCW order (first point not repeated at the end).
  This lab's stand-in for a real floorplan polygon: a convex hull is a
  reasonable outline estimator for a convex room from a noisy wall-point
  cloud, but it WILL clip concave rooms (L-shapes etc.) -- documented
  future work is a concave alpha-shape / occupancy-grid outline instead
  (see README)."
  [points]
  (let [pts (vec (sort-by (fn [[x y]] [x y]) (distinct (map vec points))))]
    (if (< (count pts) 3)
      pts
      (let [lower (build-half-hull pts)
            upper (build-half-hull (rseq pts))]
        (vec (concat (pop lower) (pop upper)))))))

(defn floorplan-from-points
  "Estimate a room outline from wall POINTS via `convex-hull`. The
  top-level entry point for this lab's \"algorithms -> floorplan\"
  pipeline (see also `collect-wall-points` to build POINTS from a
  trajectory + sonar readings)."
  [points]
  (convex-hull points))
