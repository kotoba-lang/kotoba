(ns kami-app-giemon-factory
  "kami-app-giemon-factory — the giemon robot line (arm6 + kabitori) factory,
  restored as a zero-dep portable CLJC domain data model.

  Restored from the legacy `kami-app-giemon-factory` Rust crate
  (`kotoba-lang/kami-engine`, `src/lib.rs` + `src/scene.rs`, deleted in PR #82
  \"Remove Rust workspace from kami-engine\"), per ADR-2607010930
  (`com-junkawasaki/root`).

  The original crate was two `wasm-bindgen` entry points
  (`run_giemon_factory_v1` — the completed plant with live arm6 work-cells and
  free-roaming AGVs; `run_giemon_factory_build_v1` — a 4D construction-order
  playback) built on top of a hand-authored factory scene
  (`70-tools/e7m-sim/scenes/giemon-factory-r0/*.json`, not present anywhere in
  this monorepo checkout — confirmed absent by a tree search of the source
  commit before this port began).

  This restoration ports the genuinely portable **domain data model** —
  factory layout, 4D construction order, robot roster, and engineering
  clashes — plus the pure derivation/validation functions the Rust crate (and
  its own `#[cfg(test)]` suite) defined over that data. See each namespace's
  docstring for its exact `scene.rs` provenance.

  | Namespace | Ports |
  |---|---|
  | `kami-app-giemon-factory.factory` | `Factory` layout data + `center`, `site-extent`, `wall-obstacles`, `column-obstacles`, `machine-obstacles`, `agv-obstacles`, `element-xy`, `step-center`, `element-ids`. |
  | `kami-app-giemon-factory.construction-order` | `ConstructionOrder`/`OrderStep` data + `programme-days`, plus `seq-contiguous?`/`reveals-resolve?`/`steps-resolve-robots?` (inlined from the Rust test suite's parity checks — genuine order-validity logic, not just test code). |
  | `kami-app-giemon-factory.robots` | `Robots`/`Robot` data + `by-id` (the Rust `get`). |
  | `kami-app-giemon-factory.clashes` | `Clashes`/`Clash` data + `valid?`, `hard`, `coordination`. |

  **Excluded entirely** (native-only, no portable logic — same class of
  scoping decision as `kotoba-lang/kami-app-isekai` and the sibling
  `kotoba-lang/kami-app-sarutahiko-factory`, which restored the same
  giemon-factory pattern):

  - The `#[wasm_bindgen]` entry points `run_giemon_factory_v1` /
    `run_giemon_factory_build_v1` and their HUD status bridges
    (`giemonFactoryStep`, `giemonFactoryClashCount`, the `thread_local!`
    cell) — WASM/browser glue.
  - `static_boxes` + the colour lookup tables (`machine_color`,
    `utility_color`, `site_color`, the `C_*` constants) and
    `cell_body_world` — mesh-building / render-only; id-tagged unit-box
    geometry has no meaning outside a renderer.
  - `ArmCell` (arm6 work-cell physics) and `Agv` (4-DOF AGV chassis
    physics) — both PD-control step against `kami_genesis`
    `Articulation3dConfig`/`Articulation3dState`/`ContactWorld`. No kotoba
    port of the kami-genesis rigid-body/articulation contact solver exists
    anywhere in `kotoba-lang` (checked before this port began), so this
    stays Rust.
  - `arm6_config()` / `ARM6_URDF` (`giemon_arm6.urdf` parsing) and
    `agent_urdf` (AGV URDF generation) — URDF↔articulation-config plumbing
    is solver-adjacent adapter code with no standalone portable value.

  No network, no I/O in this namespace or `factory`/`construction-order`/
  `robots`/`clashes`. Portable across JVM / ClojureScript / SCI / GraalVM."
  (:require [kami-app-giemon-factory.factory :as factory]
            [kami-app-giemon-factory.construction-order :as construction-order]
            [kami-app-giemon-factory.robots :as robots]
            [kami-app-giemon-factory.clashes :as clashes]))

(def ^:const crate-name
  "The original Rust crate this repo restores."
  "kami-app-giemon-factory")

(def ^:const source-commit
  "The kotoba-lang/kami-engine commit the Rust source was recovered from."
  "a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa")

(def ^:const deleted-in-pr
  "The kotoba-lang/kami-engine PR that deleted the Rust workspace."
  82)
