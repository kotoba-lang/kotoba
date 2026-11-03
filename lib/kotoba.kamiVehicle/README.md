# kami-vehicle

BeamNG-grade soft-body vehicle physics, restored as a portable
**zero-dependency CLJC** library.

Restored from `kami-vehicle` (`kotoba-lang/kami-engine`, deleted in PR #82,
"Remove Rust workspace"), per ADR-2607010930 (kami-engine crate
restoration, owner decision 2026-07-02).

## Why this exists

`kami-engine` originally shipped a Rust workspace implementing a BeamNG-style
soft-body vehicle simulator (nodes + beams + XPBD solver + Pacejka tire
model + a full sedan reference model). The Rust workspace was deleted in
PR #82. This repository ports that crate's logic to portable Clojure/CLJC
so it runs unmodified on JVM Clojure, ClojureScript, and babashka, with
**no external dependencies** — everything (including the 3-vector math
that stood in for `glam::Vec3`) is implemented from scratch in this repo.

## Module map

Each namespace under `src/vehicle/` is a direct, namespace-for-namespace
port of the corresponding original Rust module. Dependency arrows point
from lower-level to higher-level modules; each is listed together with
what it restores:

| Namespace | Restores | Depends on |
|---|---|---|
| `vehicle.vec3` | `glam::Vec3` stand-in (map-based `{:x :y :z}` vectors) | -- |
| `vehicle.node` | Mass-point node (position/velocity/force/mass) | `vec3` |
| `vehicle.beam` | Spring-damper beam, incl. plastic deformation, `:normal`/`:bounded`/`:hydro`/`:pressured`/`:support` kinds | -- |
| `vehicle.triangle` | Aero / collision-hull triangle surface | -- |
| `vehicle.wheel` | Wheel hub + tire-ring node group, Pacejka magic-formula tire model | `vec3` |
| `vehicle.ground` | Ground contact resolution (`FlatGround`/`ClosureGround`/`MapGround` trait, ported as a `:sample-fn` convention) | `vec3` |
| `vehicle.integrator` | Integrator config driving the soft body forward in time (2000 Hz internal substepping) | `vec3` |
| `vehicle.implicit` | Alternate implicit-Euler + Conjugate Gradient integrator | `vec3`, `node`, `beam` |
| `vehicle.rigid-chassis` | Shape-matching rigid-chassis projection for body/cargo nodes | `vec3`, `node` |
| `vehicle.powertrain` | Engine torque curve, clutch, gearbox, differential, driveline | -- |
| `vehicle.controls` | Normalised driver inputs (throttle/brake/handbrake/clutch/steer/gear) | -- |
| `vehicle.jbeam` | Hand-written JBeam-subset loader (parses pre-parsed EDN/Clojure maps, not raw JSON, to preserve the zero-dependency requirement) | `node`, `beam`, `wheel` |
| `vehicle.builder` | Programmatic vehicle builder (id-allocating, immutable, threaded via `[builder id]` returns) | `vec3`, `node`, `beam`, `triangle` |
| `vehicle.vehicle` | Composite soft-body `Vehicle` with `step` — the main XPBD simulation loop | most of the above |
| `vehicle.models.sedan` | Reference sedan model (~86 nodes, ~220 beams, matches BeamNG "Pessima" structural granularity) | `vehicle`, `wheel`, `powertrain` |
| `vehicle.models.garage` | Preset library of buildable vehicle kinds (sedan/hatchback/suv/sports/pickup/bus) | `vehicle`, `powertrain`, `wheel`, `models.sedan` |
| `vehicle` (root) | Mirrors the original `lib.rs` module list; top-level re-exports for convenience | all of the above |

## Tests

Each `src/vehicle/**.cljc` namespace has a matching test namespace under
`test/`. Run with:

```sh
kbb -M:test
```

Current status: **56 tests, 131 assertions, 0 failures, 0 errors.**

## Zero-dependency guarantee

`deps.edn` declares no runtime dependencies — only the `:test` alias pulls
in `cognitect-labs/test-runner` as a dev-time test harness. All vector
math, physics integration, and parsing logic is implemented directly in
this repo.
