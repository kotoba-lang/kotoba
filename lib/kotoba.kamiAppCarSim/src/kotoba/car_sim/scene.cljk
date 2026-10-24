(ns kotoba.car-sim.scene
  "Garage + ground-map + demo-circuit ASSEMBLY — the pure config-selection
  layer of `kami-app-car-sim`'s public demo (`driver.etzhayyim.com`),
  ported per ADR-2607010000. This is the direct analogue of the Rust
  `run_car_sim` boot sequence (`src/lib.rs`) minus everything that isn't
  pure config selection: no wgpu pipeline construction, no JS-global
  reads, no live `Vehicle` instantiation/stepping (that needs the
  soft-body physics solver, which belongs to the separately restored
  `kotoba-lang/kami-vehicle` CLJC repo — see `kotoba.car-sim.garage`'s
  namespace doc).

  A host adapter (e.g. a WASM app wired to `kotoba-lang/vehicle` once it
  lands) is expected to: call `boot-config` once to resolve vehicle +
  ground selection into concrete specs, hand `:garage-spec` /
  `:ground-map` to the physics layer to build the real simulated vehicle
  + ground (the restored portable implementation is `kotoba-lang/kami-vehicle`),
  then drive the per-frame loop with `kotoba.car-sim.controls`
  + `kotoba.car-sim.ground/sample`.

  Pure data in, pure data out: no network, no I/O. Portable across
  JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.car-sim.color :as color]
            [kotoba.car-sim.garage :as garage]
            [kotoba.car-sim.ground :as ground]))

(def default-vehicle-id :sedan)
(def default-paint-hex "#da3340")
(def default-map ground/demo-circuit)

;; Mirrors `run_car_sim`'s pre-warm setup: force XPBD (the Rust comment
;; notes the Implicit integrator's stiffness-matrix sign "still needs more
;; work"), start in 1st gear with the clutch/shift fully settled.
(def default-integrator-mode :xpbd)
(def initial-gearbox-state {:current-gear 1 :shift-progress 1.0})

(defn boot-config
  "Resolve a car-sim boot request into a fully-assembled, pure scene
  config: `{:vehicle-kind :garage-spec :paint :ground-map
  :integrator-mode :gearbox-state}`. `opts` (all optional):
    `:vehicle-id`  — any id form `garage/vehicle-kind` accepts; default `:sedan`.
    `:paint-hex`   — `#rrggbb` string; default `\"#da3340\"`.
    `:ground-map`  — a map shaped like `ground/demo-circuit`; default that circuit.
  Mirrors the config-selection half of Rust `run_car_sim` (vehicle kind +
  paint from JS globals, `kami_vehicle_scene::build_from_edn` / EDN-driven
  garage build, `shipped_demo_circuit`) — everything up to, but not
  including, actually building the soft-body `Vehicle`."
  ([] (boot-config {}))
  ([{:keys [vehicle-id paint-hex ground-map]
     :or {vehicle-id default-vehicle-id
          paint-hex default-paint-hex
          ground-map default-map}}]
   (let [kind (garage/vehicle-kind vehicle-id)]
     {:vehicle-kind kind
      :garage-spec (garage/spec-for kind)
      :paint (color/parse-color-hex paint-hex)
      :ground-map ground-map
      :integrator-mode default-integrator-mode
      :gearbox-state initial-gearbox-state})))

(defn hud-surface
  "The ground-derived slice of the Rust `__carsim_hud` telemetry payload:
  the surface under the vehicle's centre of mass and its renderer id /
  display name. `(com-x, com-z)` are the vehicle's world-space X/Z
  (supplied by the physics layer — this fn has no notion of vehicle
  state). The remaining `__carsim_hud` fields (speed/rpm/gear/broken
  beams/grounded wheels/node&beam counts) all require live physics state
  and are intentionally NOT reproduced here."
  [ground-map com-x com-z]
  (let [surface (ground/surface-at ground-map com-x com-z)]
    {:surface surface
     :renderer-id (ground/renderer-id surface)
     :name (ground/display-name surface)}))
