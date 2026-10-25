# kami-app-car-sim

[![CI](https://github.com/kotoba-lang/kami-app-car-sim/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kami-app-car-sim/actions/workflows/ci.yml)

**KAMI car-sim domain layer, in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) port (ADR-2607010000) of the
Rust `kami-app-car-sim` crate — the public BeamNG-grade soft-body vehicle
demo at [driver.etzhayyim.com](https://driver.etzhayyim.com) (~80 mass
nodes / ~220 beams, Pacejka tire model, full powertrain).

No network, no I/O. Portable `.cljc` across JVM / ClojureScript / SCI /
GraalVM.

## What this repo owns

The Rust `kami-app-car-sim` crate itself was almost entirely
wgpu-rendering / WASD-input / JS-bridge glue — the demo's *host adapter*.
It built vehicles and ground maps by calling into two separate Rust
crates, `kami-vehicle` (soft-body physics solver) and `kami-vehicle-scene`
(garage/ground EDN CONFIG, already the canonical source of truth per that
crate's own `ADR-0038`). This port therefore focuses on that data +
assembly layer:

| Namespace | Ported from | Contents |
|---|---|---|
| `kotoba.car-sim.garage` | `kami-vehicle-scene/data/garage.edn` + `garage.rs` | 6 vehicle specs (sedan/hatchback/suv/sports/pickup/bus), engine torque curves, gearbox ratios, Pacejka tire presets, `spec-for` (id -> fully-resolved spec with per-kind overrides applied) |
| `kotoba.car-sim.ground` | `kami-vehicle-scene/data/ground.edn` + `kami-vehicle/src/ground.rs` | 8 surface kinds (dry/wet asphalt, gravel, sand, snow, ice, mud, grass) with friction/grip/tint, the `demo-circuit` 9-zone map, `surface-at` / `sample` |
| `kotoba.car-sim.scene` | `run_car_sim`'s config-selection half (`src/lib.rs`) | `boot-config` — vehicle-kind + paint + ground-map resolution into one pure config map; `hud-surface` |
| `kotoba.car-sim.controls` | `on_update`'s clamp/one-shot-command logic (`src/lib.rs`) | `clamp-controls`, `resolve-gear-request`, `interpret-detach-repair` |
| `kotoba.car-sim.color` | pure numeric utils in `src/lib.rs` | `parse-color-hex`, `f32->f16-bits` (HDR sky-cubemap packing) |
| `kotoba.car-sim` | — | convenience re-exports + this file's scope note |

```clojure
(require '[kotoba.car-sim :as car-sim])

(car-sim/spec-for :sports)
;; => {:kind :sports :wheelbase 2.55 .. :effective-max-rpm 7800.0
;;     :tire-spec {:d-long 1.20 :d-lat 1.20 ..} ..}

(car-sim/boot-config {:vehicle-id "sedan" :paint-hex "#da3340"})
;; => {:vehicle-kind :sedan :garage-spec {..} :paint [0.85 0.20 0.25]
;;     :ground-map {...demo-circuit...} :integrator-mode :xpbd
;;     :gearbox-state {:current-gear 1 :shift-progress 1.0}}

(car-sim/surface-at car-sim/demo-circuit 15.0 0.0) ;; => :sand
```

## What's NOT ported (and why)

* **Soft-body node/beam mesh generation, the XPBD/implicit solver, and the
  Pacejka tire-force math.** This is core vehicle physics, not app-layer
  config — it belongs to the (separate, not-yet-ported as of this port)
  `kami-vehicle` physics crate/repo. `garage/spec-for` resolves a vehicle
  kind into exactly the config a physics builder needs to instantiate a
  real vehicle from; `kotoba-lang/vehicle` (once it lands) is the intended
  dependency for that step.
* **wgpu pipeline construction + `shader.wgsl`.** Three render pipelines
  (beam wireframe, filled body panels, procedural multi-zone ground) plus
  a baked Rayleigh-sky HDR cubemap (`kami-atmosphere`) — all
  rendering/host-adapter concerns with no portable pure-Clojure
  equivalent attempted here.
* **WASD/mouse input handling and the `window.__carsim_*` JS bridge.**
  Reading raw browser globals and writing HUD telemetry back to them is
  inherently host/JS-side I/O. `kotoba.car-sim.controls` ports the *pure
  middle step* (clamping + one-shot-command interpretation) so a host
  adapter only has to read raw numbers, call these functions, and apply
  the result to a real vehicle.
* **`cube_face_dir` / cubemap-face direction math and the sky-bake loop.**
  Rendering-only, depends on `kami-atmosphere` (out of scope for this repo).

## Source

Ported read-only from `kotoba-lang/kami-engine` at commit `34b72266462a`
(`kami-app-car-sim/`, `kami-vehicle-scene/`, `kami-vehicle/src/ground.rs`
and `src/models/garage.rs` — all deleted from that repo's working tree,
uncommitted, per the ADR-2607010000 migration). `garage.edn`/`ground.edn`
values are byte-identical to the mirrors already tracked in
`kotoba-lang/kami-scene-contracts/resources/kami/scene/contracts/kami-vehicle-scene/`.

## License

Apache License 2.0.
