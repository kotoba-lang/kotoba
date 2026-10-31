(ns vehicle.integrator
  "Integrator config -- drives the soft body forward in time.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   BeamNG runs the soft body at 2000 Hz internally and renders at 60+ Hz.
   Each call to `step(dt)` is one render tick and internally substeps to
   keep `internal_dt <= max_dt` (default 0.5 ms)."
  (:require [vehicle.vec3 :as v3]))

(defn default-config []
  {:gravity (v3/v3 0.0 -9.81 0.0)
   :max-dt 5e-4
   :max-substeps 64})

(defn substep-count
  "Compute how many substeps fit into `dt` while staying within `max-dt`.
   Returns `[n sub-dt]`."
  [dt cfg]
  (if (<= dt 0.0)
    [0 0.0]
    (let [n (long (Math/ceil (/ dt (:max-dt cfg))))
          n (max 1 (min n (:max-substeps cfg)))]
      [n (/ dt n)])))
