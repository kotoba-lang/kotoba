(ns autodrive.estimator
  "Dead-reckoning state estimator.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  Integrates body-frame inertial/odometry measurements — longitudinal
  acceleration and yaw rate (what an IMU + wheel odometry give after gravity
  compensation) — between sparse absolute pose fixes (GNSS / SLAM /
  lidar-localisation), correcting toward each fix with a complementary
  filter. This keeps a usable pose estimate when absolute localisation drops
  out, and is the natural feed for `autodrive.autopilot/step` when the true
  pose isn't directly observable.

  # Example

      (def est (new-estimator (autodrive.types/pose2 0.0 0.0 0.0)))
      ;; 1 s of straight-line IMU at 2 m/s^2 (no turn).
      (def est (reduce (fn [e _] (predict e 2.0 0.0 (/ 1.0 100))) est (range 100)))
      (< (Math/abs (- (speed est) 2.0)) 1e-3) ;=> true
      ;; An absolute fix snaps the estimate back onto truth.
      (def est (correct est (autodrive.types/pose2 0.9 0.0 0.0) 1.0))
      (< (Math/abs (- (:x (pose est)) 0.9)) 1e-4) ;=> true"
  (:require [autodrive.types :as t]))

(def ^:private PI #?(:clj Math/PI :cljs js/Math.PI))

(defn new-estimator
  ([initial] (new-estimator initial 0.0))
  ([initial speed] {:pose initial :speed speed}))

(defn pose [e] (:pose e))
(defn speed [e] (:speed e))

(defn- wrap-pi
  "Wrap an angle to (-pi, pi]."
  [a]
  (let [x (mod a (* 2.0 PI))
        x (if (> x PI) (- x (* 2.0 PI)) x)]
    (if (<= x (- PI)) (+ x (* 2.0 PI)) x)))

(defn predict
  "Propagate the estimate forward by `dt` under a body longitudinal accel
  (m/s^2) and yaw rate (rad/s) — one IMU/odometry sample."
  [e accel yaw-rate dt]
  (let [speed (+ (:speed e) (* accel dt))
        p (:pose e)
        yaw (+ (:yaw p) (* yaw-rate dt))
        s (Math/sin yaw) c (Math/cos yaw)
        x (+ (:x p) (* speed c dt))
        y (+ (:y p) (* speed s dt))]
    (assoc e :speed speed :pose (t/pose2 x y yaw))))

(defn correct
  "Pull the estimate toward an absolute pose `fix` (`gain` in [0,1]; 1 = snap
  to the fix, 0 = ignore). Yaw uses the shortest-arc blend."
  [e fix gain]
  (let [g (min 1.0 (max 0.0 gain))
        p (:pose e)
        x (+ (:x p) (* (- (:x fix) (:x p)) g))
        y (+ (:y p) (* (- (:y fix) (:y p)) g))
        yaw (+ (:yaw p) (* (wrap-pi (- (:yaw fix) (:yaw p))) g))]
    (assoc e :pose (t/pose2 x y yaw))))

(defn correct-speed
  "Blend a measured speed (e.g. wheel odometry) into the estimate."
  [e measured gain]
  (update e :speed + (* (- measured (:speed e)) (min 1.0 (max 0.0 gain)))))
