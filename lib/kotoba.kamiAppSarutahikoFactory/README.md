# kotoba-sarutahiko-factory

**猿田彦 (sarutahiko) Class-8 cargo truck assembly plant, in pure Clojure.**
A [kotoba-lang](https://github.com/kotoba-lang) domain port of the Rust
`kami-app-sarutahiko-factory` crate (`orgs/kotoba-lang/kami-engine`), per
ADR-2607010000 (`kotoba-runtime-sdk-cljc-migration`). The plant designs
the 猿田彦 truck end-to-end in kami-engine + kotoba EAVT (ADR-2606013100 /
ADR-2605252500) and reuses the giemon-factory 4D-BIM construction-sequence
playback pattern (ADR-2606010030, shared with the sibling `kami-app-tatekata`
crate, ported separately).

This library owns the *domain data model*: factory layout (buildings /
zones / machines / MEP / site), the 4D construction order, the robot
roster, the production-line station schedule, the 積込ロボット (finished-
truck loading robot) static logistics config, and engineering-clash
records — plus pure derivation/validation functions over that data. It
does **not** own wgpu rendering, `wasm_bindgen` entry points, or physics
stepping; see "Unported" below.

No network, no I/O in the domain namespaces. Portable `.cljc` across JVM /
ClojureScript / SCI / GraalVM.

## Namespaces

| Namespace | Ports (from `scene.rs` unless noted) |
|---|---|
| `kotoba.sarutahiko-factory` | Parent overview + static plant identity metadata. |
| `kotoba.sarutahiko-factory.factory` | `Factory` — layout data + `center`, `site_extent`, `wall_obstacles`, `column_obstacles`, `machine_obstacles`, `carrier_deck`, `element_xy`, `agv_obstacles`, plus an `element-ids` helper (inlined from the Rust test suite's id-set construction, since it's genuinely reusable domain logic: validating that a construction order only reveals real elements). |
| `kotoba.sarutahiko-factory.construction-order` | `ConstructionOrder` / `OrderStep` — `programme_days`, plus `seq-contiguous?` / `reveals-resolve?` / `steps-resolve-robots?` (ported from the Rust test suite's parity checks, since they are reusable order-validity logic, not just test code). |
| `kotoba.sarutahiko-factory.robots` | `Robots` / `Robot` — `get` (as `by-id`), plus `ids` / `mobile` / `by-process`. |
| `kotoba.sarutahiko-factory.prod-order` | `ProdOrder` / `ProdStation` — station schedule data + `seq-contiguous?` / `first-op` / `last-op` / `has-op?` / `stations-resolve-cells?`. |
| `kotoba.sarutahiko-factory.loader` | `Loader` (static config only — see "Unported") + `valid?` / `references-known-vehicle?` / `near-carrier?`. |
| `kotoba.sarutahiko-factory.clashes` | `Clashes` / `Clash` + `valid?` / `hard` / `coordination`. |
| `kotoba.sarutahiko-factory.fixtures` | **`.clj`-only** (not `.cljc`): JVM resource loader for this repo's synthetic EDN fixtures. The one I/O namespace in the repo. |

One namespace per exported `scene.rs` type, rather than a single flat
namespace, because each type has its own small cluster of pure
derivation/validation functions and keeping them separate matches how
callers actually use the Rust API (`scene::Factory`, `scene::Robots`,
etc. are independently constructed/queried). `kotoba.sarutahiko-factory`
itself stays a thin overview + static identity metadata, mirroring
`kotoba-lang/giemon`'s top-level namespace shape.

## Contract

```clojure
(require '[kotoba.sarutahiko-factory.factory :as factory]
         '[kotoba.sarutahiko-factory.construction-order :as co]
         '[kotoba.sarutahiko-factory.robots :as robots]
         '[kotoba.sarutahiko-factory.prod-order :as po]
         '[kotoba.sarutahiko-factory.loader :as loader]
         '[kotoba.sarutahiko-factory.clashes :as clashes]
         '[kotoba.sarutahiko-factory.fixtures :as fixtures])

(def f (fixtures/factory))               ; caller supplies the data; this repo's copy is synthetic
(factory/center f)                       ; => [50.0 25.0 0.0]
(factory/agv-obstacles f)                ; walls + columns + machines, as AABBs
(factory/element-xy f "carrier_1")       ; => [86.0 17.5]

(def order (fixtures/construction-order))
(co/programme-days order)                ; nominal build length, days
(co/reveals-resolve? order (factory/element-ids f))
(co/steps-resolve-robots? order (robots/ids (fixtures/robots)))

(def pl (fixtures/prod-order))
(po/first-op pl)                         ; => "receive"
(po/last-op pl)                          ; => "ship"

(doseq [l (:factory/loaders f)]
  (loader/valid? l)
  (loader/references-known-vehicle? l (map :id (:factory/machines f)))
  (loader/near-carrier? l (:factory/machines f)))

(clashes/valid? (fixtures/clashes))
```

## Fixtures — real dataset unavailable, synthetic data ships instead

The original Rust crate's `scene.rs` loaded its data via `include_str!`
from `70-tools/e7m-sim/scenes/sarutahiko-factory-r0/{factory.scene,
construction.order, clashes, robots, production.order}.json`. **That
dataset is not present anywhere in this monorepo checkout** — confirmed
absent by a broad search across `orgs/` before this port began, not
something this port failed to locate. Fabricating a plausible-looking
"real" dataset would misrepresent the actual 猿田彦 plant, so this repo
instead ships small hand-authored synthetic fixtures under
`resources/kotoba/sarutahiko-factory/*.edn` (a four-wall/four-column
building shell, a 4-step construction order, a 3-robot roster, a 5-station
production line, two loaders, two engineering clashes) and tests the same
*kinds* of properties the original Rust test suite checked (parses;
`:step/reveals` resolve; `:step/robot` resolves in the roster; obstacle
counts match input counts; station sequence is contiguous with `receive`
first / `ship` last; loader config references a real machine and sits
near a real carrier; clash coordinates are finite) — against synthetic
data, not the real plant.

## Unported (host-adapter, stays Rust+wgpu)

- **`#[wasm_bindgen]` entry points** (`run_sarutahiko_factory_v1`,
  `run_sarutahiko_factory_build_v1`, `run_sarutahiko_factory_load_v1`,
  `run_sarutahiko_factory_produce_v1`) — WASM/browser glue, not domain
  logic.
- **`static_boxes` + colour lookup tables** (`machine_color`,
  `utility_color`, `site_color`, the `C_*` constants) — mesh-building /
  render-only; id-tagged unit-box geometry has no meaning outside a
  renderer.
- **`ArmCell` (arm6 work-cell physics)** — kami-genesis
  `Articulation3dConfig`/`Articulation3dState`/`ContactWorld` PD-control
  stepping. No kotoba port of the kami-genesis rigid-body/articulation
  contact solver exists anywhere in `kotoba-lang` yet (verified before
  this port began), so this stays Rust.
- **`Agv` (physics chassis) / `LoaderRobot` / `ProductionLine` stepping
  logic** — the *choreography* (drive-toward, kinematic carry, settle-
  onto-deck contact) is physics simulation over the same unported
  solver. Only the **static config data** these consume is ported: the
  `Loader` struct fields (`kotoba.sarutahiko-factory.loader`) and the
  `ProdStation` schedule (`kotoba.sarutahiko-factory.prod-order`).
- **`arm6_config()` / `giemon_arm6.urdf` parsing** — URDF→articulation
  parsing is solver-adjacent adapter code. (The fixture itself,
  `giemon_arm6.urdf`/`.edn`, is already available as a reference at
  `orgs/kotoba-lang/giemon/fixtures/giemon_arm6/` if a future articulation
  port needs it.)
- **HUD status bridges** (`sarutahikoFactoryStep`, `sarutahikoLoadPhase`,
  `sarutahikoProduceLabel`, `sarutahikoFactoryClashCount`, the
  `thread_local!` state cells) — host-side UI plumbing.

## Why one repo per `kami-app-*` crate

Per ADR-2607010000, `kami-engine`'s `kami-app-*` crates are being demoted
from "engine semantics authority" to "adapter that executes a kotoba
contract." Each app's pure domain data model gets its own kotoba
`.cljc` repo; the Rust crate keeps only launch + frame-loop + adapter
binding.

## License

Apache License 2.0.
