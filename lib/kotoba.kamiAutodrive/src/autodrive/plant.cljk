(ns autodrive.plant
  "Dynamics plants the autonomy loop can drive.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  The `Plant` seam between the GNC stack and a vehicle body is a plain
  Clojure protocol here. `bicycle-model` is the shared kinematic plant used
  by ship/drone/aircraft (and as a fast reference for the car). The original
  crate's high-fidelity car plant (`vehicle_adapter.rs`, feature
  `soft-body-car`) is excluded — see the README for rationale; it wraps the
  external `kami-vehicle` soft-body physics engine with no portable content
  of its own beyond that glue."
  (:require [autodrive.types :as t]))

(defprotocol Plant
  "Anything the autopilot can sense + actuate."
  (pose [this])
  (speed [this])
  (step [this cmd dt] "Advance the plant by `dt` under `cmd`; returns the new plant."))

;; ─────────────────────────────── BicycleModel ───────────────────────────────

(defrecord BicycleModel [pose speed limits drag]
  Plant
  (pose [this] (:pose this))
  (speed [this] (:speed this))
  (step [this cmd dt]
    (let [cmd (t/clamp-cmd cmd)
          l (:limits this)
          spd (:speed this)
          accel (if (:reverse cmd)
                  (- (- (* (:throttle cmd) (:max-accel l))) (* (:drag this) spd))
                  (- (* (:throttle cmd) (:max-accel l))
                     (* (:brake cmd) (:max-decel l))
                     (* (:drag this) spd)))
          min-speed (if (:reverse cmd) (* -0.12 (:max-speed l)) 0.0)
          spd (min (:max-speed l) (max min-speed (+ spd (* accel dt))))
          spd (if (> (:handbrake cmd) 0.5) (* spd (- 1.0 (min 1.0 (* 0.9 dt)))) spd)
          delta (* (:steer cmd) (:max-steer l))
          yaw-rate (if (> (:wheelbase l) 1e-3) (* (/ spd (:wheelbase l)) (Math/tan delta)) 0.0)
          p (:pose this)
          yaw' (+ (:yaw p) (* yaw-rate dt))
          s (Math/sin yaw') c (Math/cos yaw')
          x' (+ (:x p) (* spd c dt))
          y' (+ (:y p) (* spd s dt))]
      (assoc this :pose (t/pose2 x' y' yaw') :speed spd))))

(defn bicycle-model [pose limits] (->BicycleModel pose 0.0 limits 0.05))
