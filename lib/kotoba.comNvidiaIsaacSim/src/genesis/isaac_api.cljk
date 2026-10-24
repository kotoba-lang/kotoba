(ns genesis.isaac-api
  "`isaacsim.core.api`-shaped facade (`IsaacWorld`, `ArticulationView`,
  `ArticulationViewMut`, `ArticulationControllerView`) — clean-room mirror
  of the Isaac Sim 4.x surface, no NVIDIA library linked.

  The original `isaac_api.rs` is a thin wrapper around
  `genesis.world`'s `World`/`Articulation` (`kami_articulated`-URDF-driven,
  out of scope here — see `genesis.world`) plus `genesis.controllers`. It
  adds no numerical logic of its own; every method delegates straight
  through to the wrapped `World`/`Articulation`/`ArticulationController`.
  This facade owns a live pure `genesis.world` container. It supports adding
  generic 3-D articulations, queuing their efforts, stepping all of them with
  the clock, resetting, and retrieving link state. Python's actual Isaac Sim
  runtime remains available separately in `python/isaac_sim_6_smoke.py`.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/isaac_api.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930."
  (:require [genesis.world :as world]))

(defn new-isaac-world [physics-dt]
  {:physics-dt physics-dt :time-step-index 0
   :world (assoc (world/default-world) :dt physics-dt)})

(defn get-physics-dt [w] (:physics-dt w))
(defn current-time-step-index [w] (:time-step-index w))
(defn current-time [{:keys [physics-dt time-step-index]}] (* physics-dt time-step-index))

(defn add-articulation [w name cfg]
  (update w :world world/add-articulation name cfg))

(defn set-articulation-efforts [w name efforts]
  (update w :world world/set-articulation-efforts name efforts))

(defn get-articulation [w name]
  (world/articulation (:world w) name))

(defn get-link-state [w articulation-name link-name]
  (world/articulation-link-state (:world w) articulation-name link-name))

(defn step
  "Advance all registered articulations and then the Isaac-style clock."
  [w]
  (-> w (update :world world/step-articulations) (update :time-step-index inc)))

(defn reset
  "Rewind the clock (`current_time`/`current_time_step_index` reset to 0),
  mirroring `isaacsim.core.api.World.reset()`."
  [w] (assoc w :time-step-index 0 :world (world/reset (:world w))))
