# kotoba-lang/kami-app-giemon-factory

The bounded construction-order safety decision also has a native,
capability-free `.kotoba` kernel. Factory/clash geometry, physical robots,
rendering, source loading, and open string metadata remain Kami engine/CLJC
responsibilities.

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-app-giemon-factory`
Rust crate (`src/lib.rs` + `src/scene.rs`, deleted in kotoba-lang/kami-engine PR #82
"Remove Rust workspace from kami-engine") as part of the **clj-wgsl migration**
(ADR-2607010930, `com-junkawasaki/root`).

## What this is

The original crate was two `wasm-bindgen` entry points over one hand-authored scene
(`70-tools/e7m-sim/scenes/giemon-factory-r0/`): `run_giemon_factory_v1` — the
completed plant, with live arm6 work-cells (fixed-base `Articulation3d` running a PD
work cycle) and free-roaming 4-DOF AGV carts colliding with walls/columns/machines —
and `run_giemon_factory_build_v1` — a 4D 建築手順 playback that reveals every element
in `construction.order.json` `:seq` order. Both are native WASM/wgpu/`kami_genesis`
physics substrate with no meaningful portable representation as whole programs.

Rather than attempt a 1:1 port of the tick loops (which would carry no computational
value without the native `kami_genesis` articulation/contact solver they run against —
no kotoba port of that solver exists anywhere in `kotoba-lang`, confirmed before this
port began), this restoration extracts the genuinely portable **domain data model**:
factory layout, 4D construction order, robot roster, and engineering clashes, plus the
pure derivation/validation functions the Rust crate (and its own `#[cfg(test)]` suite)
defined over that data.

| Namespace | From | Purpose |
|---|---|---|
| `kami-app-giemon-factory.factory` | `scene.rs` `Factory` | Layout data + `center`, `site-extent`, `wall-obstacles`, `column-obstacles`, `machine-obstacles`, `agv-obstacles`, `element-xy`, `step-center`, `element-ids`. |
| `kami-app-giemon-factory.construction-order` | `scene.rs` `ConstructionOrder`/`OrderStep` | Order data + `programme-days`, plus `seq-contiguous?`/`reveals-resolve?`/`steps-resolve-robots?` (inlined from the Rust test suite's own parity checks — genuine order-validity logic, not just test scaffolding). |
| `kami-app-giemon-factory.robots` | `scene.rs` `Robots`/`Robot` | Roster data + `by-id` (the Rust `Robots::get`). |
| `kami-app-giemon-factory.clashes` | `scene.rs` `Clashes`/`Clash` | Clash records + `valid?`, `hard`, `coordination` (inlined from the Rust `clashes_load` test). |

This mirrors the sibling `kotoba-lang/kami-app-sarutahiko-factory` port, which
restored the exact same giemon-factory pattern for its own plant, and follows the same
scoping method as `kotoba-lang/kami-app-isekai`.

**Excluded entirely** (native-only, no portable logic):

- The `#[wasm_bindgen]` entry points `run_giemon_factory_v1` / `run_giemon_factory_build_v1`
  and their HUD status bridges (`giemonFactoryStep`, `giemonFactoryClashCount`, the
  `thread_local!` cell) — WASM/browser glue.
- `static_boxes` + the colour lookup tables (`machine_color`, `utility_color`,
  `site_color`, the `C_*` constants) and `cell_body_world` — mesh-building/render-only;
  id-tagged unit-box geometry has no meaning outside a renderer.
- `ArmCell` (arm6 work-cell physics) and `Agv` (4-DOF AGV chassis physics) — both
  PD-control step against `kami_genesis::{Articulation3dConfig, Articulation3dState,
  ContactWorld}`. No kotoba port of the kami-genesis rigid-body/articulation contact
  solver exists anywhere in `kotoba-lang` (checked before this port began), so this
  stays Rust.
- `arm6_config()` / `ARM6_URDF` (`giemon_arm6.urdf` parsing) and `agent_urdf` (AGV URDF
  generation) — URDF↔articulation-config plumbing is solver-adjacent adapter code with
  no standalone portable value.

## Fixtures — real dataset unavailable, synthetic data ships instead

The original crate's `scene.rs` loaded its data via `include_str!` from
`70-tools/e7m-sim/scenes/giemon-factory-r0/{factory.scene,construction.order,clashes,
robots}.json`. That dataset is not present anywhere in this monorepo checkout —
confirmed absent by a tree search of the source commit
(`a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa`) before this port began. Fabricating a
plausible-looking "real" dataset would misrepresent the actual giemon factory plant, so
`test/kami_app_giemon_factory/fixtures.cljk` instead ships a small hand-authored
synthetic factory (four-wall/four-column building shell, one machine, one conveyor,
one arm6 cell, one AGV), a 3-step construction order, a 3-robot roster, and 2
engineering clashes — and tests the same *kinds* of properties the original Rust test
suite checked, against synthetic data, not the real plant.

## Status

Restored (scoped) — 20 tests / 69 assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
