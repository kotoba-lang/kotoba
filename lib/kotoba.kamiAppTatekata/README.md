# kotoba-tatekata

[![CI](https://github.com/kotoba-lang/kami-app-tatekata/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kami-app-tatekata/actions/workflows/ci.yml)

**建方 (tatekata) — the material-process + robot-op-sequence math for
robotic construction, in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library ported
from `kami-app-tatekata` (kami-engine, Rust), per
ADR-2607010000 (`kotoba-runtime-sdk-cljc-migration`, in the
`com-junkawasaki` superproject's `90-docs/adr/`): robotic construction of
the giemon factory, where each 4D construction step's assigned robot builds
it on kami-genesis, with concrete-deposition and weld material-process
fields.

No network, no I/O. Portable `.cljc` across JVM / ClojureScript / SCI /
GraalVM.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 16 tests, 66 assertions, all green |
| Solver honesty | `kotoba.tatekata.thermal` is a genuine 2-D FDM heat-conduction PDE, not a stand-in |
| Real upstream data | `process.json` is unavailable in this checkout; `kotoba.tatekata.process` ships a synthetic fixture for test coverage only |

## Contract

```clojure
(require '[kotoba.tatekata.deposit-field :as deposit]
         '[kotoba.tatekata.thermal :as thermal]
         '[kotoba.tatekata.weld-field :as weld]
         '[kotoba.tatekata.process :as process])

;; concrete deposition / screed-levelling height field (robot:printer steps)
(def field (deposit/make-field [0.0 0.0 8.0 8.0] 16 16 0.2))
(deposit/deposit-at field 4.0 4.0 0.6 0.05 (/ 1.0 30))
(deposit/progress field) ;=> fraction of the footprint at target level

;; 2-D transient heat-conduction PDE (explicit FDM, CFL-bounded)
(def hot-cold
  (-> (thermal/make-field 21 5 0.01 1e-4 0.0 9999.0)
      (thermal/with-bc [(thermal/dirichlet 100.0) (thermal/dirichlet 0.0)
                         thermal/neumann thermal/neumann])))
(thermal/step hot-cold -100.0 -100.0 0.0 0.01 (thermal/cfl-dt hot-cold))

;; moving heat-source weld-pass model (robot:bolter steps), built on thermal
(def w (weld/make-field 40 20.0 1450.0))
(weld/pass w 0.5 9000.0 (/ 1.0 60))
(weld/fused-fraction w)

;; robot op-sequence timeline per construction step
;; (caller supplies ops — this library does no I/O; see "Process data" below)
(def plans (process/plans ops ["step:01-foundation" "step:02-steel"]))
(process/op-at (first plans) 0.0)
(process/build-progress (first plans) 0.5)
```

## What's ported

- **`kotoba.tatekata.deposit-field`** — concrete-deposition / screed-
  levelling height field, ported 1:1 from `deposit_field.rs`. An
  application-layer coverage-progress model (no granular/MPM concrete
  rheology), same honest scope as the Rust original.
- **`kotoba.tatekata.thermal`** — ported 1:1 from
  `kami-genesis::thermal::ThermalField`. This is **not** a stand-in like
  the deposit field: it's a real 2-D transient heat-conduction PDE
  (explicit FDM, CFL-bounded) with a travelling Gaussian volumetric source,
  Dirichlet/Neumann boundary conditions, and peak-temperature fusion
  tracking — pulled in because `weld_field.rs` depends on it, and it turned
  out to be exactly the kind of "solver step, deterministic `.cljc`
  contract" ADR-2607010000 calls portable (unlike the rigid-body
  articulation/contact solver other app crates use).
- **`kotoba.tatekata.weld-field`** — moving heat-source weld-pass model for
  robotic steel fastening, ported 1:1 from `weld_field.rs`, built on
  `kotoba.tatekata.thermal`.
- **`kotoba.tatekata.process`** — the pure `StepPlan` derivation/lookup math
  (`is-build?`/`is-logistics?`/`plans`/`op-at`/`build-progress`/
  `logistics-at`), ported from `process.rs`'s logic (not its data loading —
  see below).

All four `#[test]`/`#[cfg(test)]` suites from the Rust originals
(`deposit_field.rs`, `kami-genesis/thermal.rs`, `weld_field.rs`) were ported
as direct parity tests with matching tolerances (e.g. `< 2.0` absolute,
`< 0.05` relative, `< 0.3` for a loose progress bound).

### Process data — synthetic fixture only

`process.rs` in the Rust original loaded a real `process.json`, generated
by `process_gen.py` from
`70-tools/e7m-sim/scenes/giemon-factory-r0/process.json` in the kami-engine
monorepo. That dataset is **not present** in this checkout (searched for
broadly, confirmed absent — not merely unfound). `kotoba.tatekata.process`
therefore has no loading function at all (consistent with this library's
no-I/O contract: callers supply ops data). `resources/kotoba/tatekata/process-ops.edn`
ships a small hand-authored SYNTHETIC ops fixture — two steps spanning the
same `procure -> deliver -> stage -> <build action> -> fasten -> inspect`
shape — used only by this repo's own test suite, not a substitute for the
real construction-process dataset.

## What's unported

Everything below stays a Rust+wgpu host adapter in `kami-engine`, out of
this library's scope (per ADR-2607010000, `.cljc`/EDN owns domain semantics;
render/GPU/realtime-loop code stays a host adapter):

- **`lib.rs`'s `#[cfg(target_family = "wasm")]` viewer/app glue** —
  `run_tatekata_v1`, the `giemonTatekataStatus` HUD bridge, `ArmCell`
  render/animation, and the `Agv` cart/payload floating-base physics
  (drives/falls via kami-genesis rigid-body solver): all wasm-bindgen entry
  points and frame-loop orchestration, not portable domain math.
- **`kami-app-giemon-factory`** (`Factory`/`ConstructionOrder`/`Robots`/
  `static_boxes`/`arm6_config`) — a *different* crate this one depends on
  for scene/robot data; out of scope for this port.
- **The rigid-body/articulation contact solver** (`kami_articulated`,
  `Articulation3dConfig`, `ContactWorld`, `parse_urdf`) — not ported
  anywhere in kotoba-lang yet (verified via grep across the org at port
  time).

## Namespaces

`kotoba.tatekata` is a parent overview namespace (doc only, no logic).
Domain logic lives in `kotoba.tatekata.deposit-field`,
`kotoba.tatekata.thermal`, `kotoba.tatekata.weld-field`, and
`kotoba.tatekata.process`.

## License

Apache License 2.0.
