(ns vehicle
  "kami-vehicle -- BeamNG-grade soft-body vehicle physics, restored as
   portable zero-dependency CLJC.

   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930.

   This root namespace mirrors the original `lib.rs` module list and
   provides a couple of top-level re-exports for convenience. Prefer
   requiring the individual `vehicle.*` namespaces directly in your own
   code (as this namespace does) rather than depending on re-exports.

   Quick start (ported from the original crate README):

   ```clojure
   (require '[vehicle.models.garage :as garage]
            '[vehicle.ground :as ground]
            '[vehicle.vehicle :as veh])

   (def car (garage/build :sports))
   (def track (ground/map-ground-demo-circuit))

   (def car (assoc car :controls (assoc (:controls car) :throttle 1.0)))
   (def car (assoc-in car [:powertrain :gearbox :current-gear] 1))
   (def car (assoc-in car [:powertrain :gearbox :shift-progress] 1.0))

   (def car (reduce (fn [c _] (veh/step c (/ 1.0 60.0) track)) car (range 240)))
   (println \"speed:\" (* (veh/speed car) 3.6) \"km/h\")
   ```

   Granularity (per car, reference sedan):
     * ~86 mass nodes (chassis floor / belt-line / roof / cargo / wheel
       hubs / tire rings),
     * ~220 beams (chassis frame + crush zones + suspension + tire
       side-walls + tire tread),
     * 4 wheels with Pacejka 1996 magic-formula tire model,
     * full powertrain -- engine torque curve / clutch / 6-speed gearbox /
       differential (open / locked / LSD) / FWD-RWD-AWD driveline,
     * 2 kHz internal substepping regardless of render rate,
     * plastic deformation on every beam (yield + work hardening), grouped
       break-zones,
     * JBeam-subset loader for swapping cars at runtime."
  (:require [vehicle.vec3]
            [vehicle.beam]
            [vehicle.builder]
            [vehicle.controls]
            [vehicle.ground]
            [vehicle.implicit]
            [vehicle.integrator]
            [vehicle.jbeam]
            [vehicle.models.garage]
            [vehicle.models.sedan]
            [vehicle.node]
            [vehicle.powertrain]
            [vehicle.rigid-chassis]
            [vehicle.triangle]
            [vehicle.vehicle]
            [vehicle.wheel]))
