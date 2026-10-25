(ns autodrive
  "kami-autodrive — vehicle-class-agnostic autonomy (GNC) layer.

  Restored (portable, zero-dependency CLJC) from the deleted `kami-autodrive`
  Rust crate (kotoba-lang/kami-engine, PR #82 \"Remove Rust workspace\"), per
  ADR-2607010930.

  This is the guidance / navigation / control stack that sits on top of
  kami-engine's simulation primitives, analogous to how an AV stack sits on
  top of a robotics simulator: the simulator provides the plant and sensors,
  the autonomy stack provides perception, planning, and control.

      lidar sweep -> perception (occupancy grid) -> planner (A*) ->
      pure-pursuit + PID control -> Command -> plant -> (new pose) -> ...

  The autopilot (`autodrive.autopilot`) is plant-agnostic: the same loop
  drives the kinematic `autodrive.plant/bicycle-model`, and the high-fidelity
  `autodrive.dynamics/ship-hydro` (Fossen hydrodynamics),
  `autodrive.dynamics/fixed-wing` (aerodynamics: lift/drag/stall/bank-to-turn),
  and `autodrive.dynamics/multirotor` (rotor thrust-vectoring + aero drag)
  plants. See `autodrive.classes` and `autodrive.dynamics` for the
  per-class fidelity map.

  ## Restored modules

  `autodrive.types`, `autodrive.classes`, `autodrive.perception`,
  `autodrive.planner`, `autodrive.control`, `autodrive.plant`,
  `autodrive.dynamics`, `autodrive.autopilot`, `autodrive.estimator`,
  `autodrive.fleet` — one namespace per original Rust module (`lib.rs`'s
  `pub mod` list), plus two new portability-only namespaces the original
  crate didn't need because it depended on external Rust crates:
  `autodrive.geom` (replaces `glam` — plain Vec2/Vec3 math) and
  `autodrive.sensor-sim` (replaces the raycasting/rendering surface of
  `kami-sensor-sim` actually needed — see its docstring).

  ## Excluded

  `vehicle_adapter.rs` (`SoftBodyCar`, feature `soft-body-car`) and its
  `tests/soft_body.rs` are excluded — both are glue code around the external
  `kami-vehicle` BeamNG-grade soft-body physics engine with no portable
  content of their own. See the README for the full rationale.

  ## Example

      (require '[autodrive.types :as t] '[autodrive.classes :as classes]
               '[autodrive.plant :as plant] '[autodrive.autopilot :as ap])

      (def start (t/pose2 0.0 0.0 0.0))
      (def car (atom (plant/bicycle-model start (classes/limits :car))))
      (def autopilot (atom (ap/new-autopilot (ap/autopilot-config :car (classes/limits :car)) start)))
      (swap! autopilot ap/set-goal (autodrive.geom/v2 20.0 0.0))

      (let [dt (/ 1.0 30)]
        (dotimes [_ 600]
          (when (not= :arrived (:state @autopilot))
            (let [pose (plant/pose @car)
                  [ap' cmd] (ap/step @autopilot pose (plant/speed @car) [] pose dt)]
              (reset! autopilot ap')
              (swap! car plant/step cmd dt)))))
      ;; => car has driven ~20 m along +x and the autopilot has arrived."
  (:require [autodrive.geom]
            [autodrive.types]
            [autodrive.classes]
            [autodrive.sensor-sim]
            [autodrive.perception]
            [autodrive.planner]
            [autodrive.control]
            [autodrive.plant]
            [autodrive.dynamics]
            [autodrive.autopilot]
            [autodrive.estimator]
            [autodrive.fleet]))

(def ADR "ADR that introduces this crate." "ADR-2606010600")
(def RESTORATION-ADR "ADR governing this crate's CLJC restoration." "ADR-2607010930")
(def NV-COMPAT-TARGET "nv-compat reference surface." "isaacsim")
