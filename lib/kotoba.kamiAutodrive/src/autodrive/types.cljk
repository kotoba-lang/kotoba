(ns autodrive.types
  "Core geometric + command types for the autonomy stack.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  Frame convention (ROS REP-105, z-up): the planar ground frame is `(x, y)`
  with `x` east, `y` north, and `yaw` measured counter-clockwise from `+x`. A
  vehicle at `yaw = 0` faces `+x`. This matches the portable
  `autodrive.sensor-sim` lidar sensor frame, so lidar returns drop in without
  a frame flip."
  (:require [autodrive.geom :as g]))

;; ─────────────────────────────── Pose2 ───────────────────────────────

(defn pose2
  "Planar pose: position on the ground plane plus heading (radians, CCW from
  +x)."
  [x y yaw]
  {:x x :y y :yaw yaw})

(defn pos [p] (g/v2 (:x p) (:y p)))

(defn forward
  "Unit forward (heading) vector."
  [p]
  (g/v2 (Math/cos (:yaw p)) (Math/sin (:yaw p))))

(defn left
  "Unit left vector (90 deg CCW from forward)."
  [p]
  (g/v2 (- (Math/sin (:yaw p))) (Math/cos (:yaw p))))

(defn to-local
  "Express a world point in the body frame: +x forward, +y left."
  [p world]
  (let [d (g/sub2 world (pos p))
        s (Math/sin (:yaw p))
        c (Math/cos (:yaw p))]
    (g/v2 (+ (* c (:x d)) (* s (:y d)))
          (+ (* (- s) (:x d)) (* c (:y d))))))

(defn to-world
  "Express a body-frame point (+x forward, +y left) in world coords."
  [p local]
  (let [s (Math/sin (:yaw p))
        c (Math/cos (:yaw p))]
    (g/add2 (pos p)
            (g/v2 (- (* c (:x local)) (* s (:y local)))
                  (+ (* s (:x local)) (* c (:y local)))))))

;; ─────────────────────────────── Command ───────────────────────────────

(defn command
  "Normalised actuator command.

  `:throttle` [0,1], `:brake` [0,1], `:steer` [-1,1] (positive = left/CCW),
  `:handbrake` [0,1], `:reverse` bool — when true, throttle drives the
  vehicle backward (used by the autopilot's stuck-recovery K-turn). Plants
  without a reverse gear ignore it."
  [& {:keys [throttle brake steer handbrake reverse]
      :or {throttle 0.0 brake 0.0 steer 0.0 handbrake 0.0 reverse false}}]
  {:throttle throttle :brake brake :steer steer :handbrake handbrake :reverse reverse})

(defn coast [] (command))

(defn stop
  "Full-brake, wheels-straight stop."
  []
  (command :brake 1.0))

(defn reverse-with
  "Reverse at `throttle` with `steer` (for K-turn recovery)."
  [throttle steer]
  (command :throttle throttle :steer steer :reverse true))

(defn clamp-cmd
  "Clamp a command's numeric fields into their valid ranges."
  [c]
  (-> c
      (update :throttle #(min 1.0 (max 0.0 %)))
      (update :brake #(min 1.0 (max 0.0 %)))
      (update :handbrake #(min 1.0 (max 0.0 %)))
      (update :steer #(min 1.0 (max -1.0 %)))))

;; ─────────────────────────────── Obstacle ───────────────────────────────

(defn obstacle
  "A circular obstacle on the ground plane (post-clustering perception output)."
  [center radius]
  {:center center :radius radius})
