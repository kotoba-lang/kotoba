(ns kotoba.car-sim
  "KAMI car-sim — public soft-body vehicle demo (`driver.etzhayyim.com`),
  domain layer ported from the Rust `kami-app-car-sim` crate
  (ADR-2607010000: kami-engine's Rust game-engine workspace is being
  retired in favour of pure Clojure `.cljc` authority repos).

  ## Scope

  The Rust `kami-app-car-sim` crate itself was almost entirely
  wgpu-rendering / WASD-input / JS-bridge glue (a BeamNG-grade soft-body
  vehicle sim's *host adapter*) — it built vehicles and ground maps by
  calling into the separate `kami-vehicle` (physics solver) and
  `kami-vehicle-scene` (garage/ground EDN CONFIG) crates. This port:

    * DOES port the pure config-selection/assembly layer: the 6 garage
      vehicle specs, the engine/gearbox/tire preset tables, the 8-surface
      grip/friction table, and the demo-circuit zone map — all sourced
      from `kami-vehicle-scene/data/{garage,ground}.edn`, the canonical
      EDN CONFIG the Rust crates already treated as their source of truth
      (`kotoba.car-sim.garage`, `kotoba.car-sim.ground`,
      `kotoba.car-sim.scene`) — plus a couple of small pure numeric
      utilities that lived directly in `kami-app-car-sim`'s own
      `src/lib.rs` (`kotoba.car-sim.color`, `kotoba.car-sim.controls`).
    * Does NOT port the soft-body node/beam mesh generation, the XPBD/
      implicit solver, or the Pacejka tire-force math — that is core
      vehicle physics belonging to the separate `kotoba-lang/kami-vehicle`
      portable CLJC authority. `garage/spec-for` resolves a vehicle kind
      into exactly the config that physics layer needs to build a real
      `Vehicle`.
    * Does NOT port wgpu pipeline construction, WGSL shaders, WASD/mouse
      input handling, or the `window.__carsim_*` JS bridge — all
      host-adapter/rendering concerns, unrelated to domain logic.

  See each sub-namespace's docstring for the precise Rust source it
  mirrors. Pure data in, pure data out throughout: no network, no I/O.
  Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.car-sim.color :as color]
            [kotoba.car-sim.controls :as controls]
            [kotoba.car-sim.garage :as garage]
            [kotoba.car-sim.ground :as ground]
            [kotoba.car-sim.scene :as scene]))

;; ── Convenience re-exports ───────────────────────────────────────────────────

(def vehicle-kinds garage/vehicle-kinds)
(def surface-kinds (keys ground/surfaces))
(def demo-circuit ground/demo-circuit)

(def spec-for garage/spec-for)
(def surface-at ground/surface-at)
(def boot-config scene/boot-config)
(def clamp-controls controls/clamp-controls)
(def parse-color-hex color/parse-color-hex)
