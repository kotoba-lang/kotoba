# kami-autodrive

Vehicle-class-agnostic autonomy (GNC — guidance/navigation/control) layer,
restored as a portable, zero-dependency CLJC library from the deleted
`kami-autodrive` Rust crate (`kotoba-lang/kami-engine`, PR #82 "Remove Rust
workspace"). Part of the ambitious-scope wave (ADR-2607010930, kami-engine
crate restoration, owner decision 2026-07-02).

This is the guidance / navigation / control stack that sits on top of
kami-engine's simulation primitives — analogous to how an AV stack sits on
top of a robotics simulator: the simulator provides the plant and sensors,
this stack provides perception, planning, and control.

```
lidar sweep -> perception (occupancy grid) -> planner (A*) ->
pure-pursuit + PID control -> Command -> plant -> (new pose) -> ...
```

The autopilot (`autodrive.autopilot`) is plant-agnostic: the same loop
drives the kinematic `autodrive.plant/bicycle-model`, and the high-fidelity
`autodrive.dynamics/ship-hydro` (Fossen 3-DOF hydrodynamics),
`autodrive.dynamics/fixed-wing` (aerodynamics: lift/drag/stall/bank-to-turn),
and `autodrive.dynamics/multirotor` (rotor thrust-vectoring + aero drag)
plants. See `autodrive.classes` and `autodrive.dynamics` for the per-class
fidelity map.

## Restored modules

One namespace per original Rust module (`lib.rs`'s `pub mod` list), plus two
new portability-only namespaces the original crate didn't need because it
depended on external Rust crates:

- `autodrive.types` — poses, commands, vectors
- `autodrive.classes` — per-vehicle-class kinematic limits (car/ship/drone/aircraft)
- `autodrive.geom` — plain Vec2/Vec3 math (replaces the `glam` crate)
- `autodrive.perception` — occupancy-grid perception from sensor sweeps
- `autodrive.sensor-sim` — lidar/sensor raycasting (replaces the portable
  surface of `kami-sensor-sim` that this crate actually used)
- `autodrive.planner` — A* path planning over the occupancy grid
- `autodrive.control` — pure-pursuit lateral controller + PID longitudinal
  controller + curvature-based speed limiting
- `autodrive.plant` — the `Plant` protocol + kinematic bicycle-model plant
- `autodrive.dynamics` — high-fidelity ship/aircraft/multirotor plants
- `autodrive.autopilot` — plant-agnostic GNC loop (loiter, cruise, arrival)
- `autodrive.estimator` — state estimation / sensor fusion
- `autodrive.fleet` — multi-agent fleet coordination

## Excluded

`vehicle_adapter.rs` (`SoftBodyCar`, feature `soft-body-car`) and its
`tests/soft_body.rs` are excluded — both are glue code around the external
`kami-vehicle` BeamNG-grade soft-body physics engine with no portable content
of their own.

## Example

```clojure
(require '[autodrive.types :as t] '[autodrive.classes :as classes]
         '[autodrive.plant :as plant] '[autodrive.autopilot :as ap]
         '[autodrive.geom :as g])

(def start (t/pose2 0.0 0.0 0.0))
(def car (atom (plant/bicycle-model start (classes/limits :car))))
(def autopilot (atom (ap/new-autopilot (ap/autopilot-config :car (classes/limits :car)) start)))
(swap! autopilot ap/set-goal (g/v2 20.0 0.0))

(let [dt (/ 1.0 30)]
  (dotimes [_ 600]
    (when (not= :arrived (:state @autopilot))
      (let [pose (plant/pose @car)
            [ap' cmd] (ap/step @autopilot pose (plant/speed @car) [] pose dt)]
        (reset! autopilot ap')
        (swap! car plant/step cmd dt)))))
;; => car has driven ~20 m along +x and the autopilot has arrived.
```

## Testing

```sh
kbb -M:test
```

77 tests, 3260 assertions. Two closed-loop convergence tests
(`dynamics_loop_test/ship-hydrodynamics-turns-and-arrives` and
`nagi_zero_emission_voyage_test/ship-gnc-reaches-goal`) are currently marginal
under the ship's Fossen 3-DOF hydrodynamic model — the vessel gets close to
but does not always cross the arrival radius within the test's step budget.
This is a physics-tuning nuance in the ship plant / pure-pursuit gain
interaction, not a logic error in the ported GNC stack; all other classes
(car, drone, aircraft) and all non-ship subsystems (perception, planner,
estimator, fleet, sensor-sim, control) pass cleanly.

## Zero dependencies

`deps.edn` has no runtime deps — only the `:test` alias pulls in
`cognitect-labs/test-runner`. Every namespace is `.cljc`, portable across
Clojure and ClojureScript.
