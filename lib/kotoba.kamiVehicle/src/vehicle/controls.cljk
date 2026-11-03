(ns vehicle.controls
  "Driver inputs.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   All inputs are normalised to [0, 1] (or [-1, 1] for steering)."
  )

(defn default-controls []
  {:throttle 0.0
   :brake 0.0
   :handbrake 0.0
   :clutch-pedal 0.0
   :steer 0.0
   :requested-gear 1
   :ignition true})

(defn coast [] (default-controls))

(defn- clamp [v lo hi] (min hi (max lo v)))

(defn clamp-inputs [controls]
  (-> controls
      (update :throttle clamp 0.0 1.0)
      (update :brake clamp 0.0 1.0)
      (update :handbrake clamp 0.0 1.0)
      (update :clutch-pedal clamp 0.0 1.0)
      (update :steer clamp -1.0 1.0)))
