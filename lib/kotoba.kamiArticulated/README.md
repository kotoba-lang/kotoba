# kami-articulated (restored)

`src/articulated_transform_golden.kotoba` is the policy-v7 qualification
slice for a bounded prismatic coordinate and the cartpole revolute joint's
world-space tip transform. Its tests derive the oracle inputs from the existing
URDF parser and compare Kotoba reference, restricted JavaScript, and typed Wasm.

`src/urdf_query.kotoba` now qualifies the bounded XML ingestion slice against
both real URDF fixtures. Link/joint names, joint kinds and topology attributes,
mass, Pose, bounded positive-semidefinite Inertia, and nominal Link/Joint
records agree with the existing CLJC parser across Kotoba reference,
restricted JavaScript, and typed Wasm. Its indexed graph validator admits
arbitrary declaration order through 128 links / 127 joints and rejects duplicate
identities, unknown references, multiple parents, self-edges, cycles,
disconnection, and every limit violation. Graphs above that sealed profile and full
`ArticulatedSystem` assembly remain later bounded profile work. The downstream
physics solver remains a separate engine provider boundary.

Zero-dependency portable CLJC restoration of the deleted `kami-articulated`
Rust crate from `kotoba-lang/kami-engine` (removed in PR #82, "Remove Rust
workspace from kami-engine"), per ADR-2607010930 (clj-wgsl migration,
`com-junkawasaki/root`). Rust source recovered at commit
`a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa`.

## What this crate was

Per the original crate docstring, `kami-articulated` was reserved as a
"URDF / MJCF / USD physics loader → kami-genesis articulation" (R1.0 path
reservation, ADR-2605261800). Only the URDF path was ever implemented, at
R1.1 PoC scope: a minimum URDF (Unified Robot Description Format) parser
supporting prismatic + revolute (+ fixed/continuous) joints, with link
mass/inertia extraction and joint axis/limits/dynamics (damping/friction),
built on the `roxmltree` XML crate (WASM-friendly) and `glam::Vec3`.

## What was ported vs excluded

**Ported** (portable, pure data transformation — reading a URDF XML robot
description into structured links + joints):

- `parse-urdf` — URDF XML string → `ArticulatedSystem` (`{:name :links
  :joints}`), 1:1 port of `src/urdf.rs`'s `parse_urdf`.
- `Pose` / `Inertia` / `Link` / `Joint` / `ArticulatedSystem` data shapes,
  as plain keyword maps.
- `link-index` / `joint-index` lookup helpers.
- The crate-level constants (`ADR`, `PHASE`, `KAMI_NAME`,
  `NV_COMPAT_TARGET`, `SUPPORTED_FORMATS`) from `lib.rs`.
- A hand-rolled minimal recursive-descent XML reader (`parse-xml`), since
  the original's `roxmltree` dependency and CLJC's zero-dep constraint
  meant XML tokenizing had to be reimplemented locally. It covers exactly
  the element/attribute subset URDF uses (no text nodes, no CDATA).

**Excluded** (native/vendor-facade, out of scope for this restoration):

- The downstream `kami-genesis` articulated rigid-body-dynamics solver
  (PxArticulationReducedCoordinate-shaped, per the original's
  `NV_COMPAT_TARGET = "isaacsim.core.prims.Articulation"`) that consumes
  the `ArticulatedSystem` this namespace produces. `kami-genesis` was never
  restored in this crate's original scope either — it stays Rust/native,
  handled (if at all) by a separate restoration effort.
- MJCF (MuJoCo XML) and USD physics schema parsing — reserved in the
  crate's scope docs but never implemented in the original Rust source, so
  there was nothing to port.

## Fixtures

- `test/fixtures/cartpole.urdf` — the Cartpole-v1 reference URDF
  (`world → [slider] → cart → [revolute] → pole_link`), copied from the
  original crate's test dependency `kami-engine/fixtures/cartpole/
  cartpole.urdf` (via `include_str!`). This is the same fixture already
  used by the restored `kotoba-lang/cartpole-wasm` and by
  `kami-app-isekai`'s omniverse module.
- `test/fixtures/hizukue.urdf` — the crate's own `urdf/hizukue.urdf`
  fixture: a 6-DoF panel-tracking/servicer robot (3 prismatic mobile-base
  DOF + 3 revolute arm DOF) for hikari solar-farm panel servicing. Used
  here as an additional real-world parse smoke test beyond what the
  original `#[test]`s exercised.

## Stats

- `src/kami_articulated.cljk` — 57 lines (root namespace, re-exports).
- `src/kami_articulated/urdf.cljk` — 344 lines (XML reader + URDF parser).
- `test/kami_articulated_test.cljk` — 103 lines.
- 6 tests / 28 assertions, 0 failures, 0 errors.
- All 4 original Rust `#[test]`s ported 1:1 (`parses_cartpole_urdf`,
  `cartpole_topology_correct`, `cartpole_masses_match_isaaclab_baseline`,
  `rejects_unknown_joint_type`), plus a namespace-loads smoke test and a
  `hizukue.urdf` parse smoke test.

## Relationship to sibling crates

- **`kotoba-lang/articulated-scene`** (restored `kami-articulated-scene`)
  is a DIFFERENT, related crate — an EDN authoring surface for robot-arm
  scenes. It originally depended on this crate's `ArticulatedSystem`/
  `Link`/`Joint`/`Inertia`/`Pose`/`JointKind` types, but since that
  restoration predates this one, it reimplemented those shapes locally as
  plain maps rather than depending on this repo.
- **`kami-genesis`** (not yet restored) is this crate's downstream
  consumer: the articulated rigid-body-dynamics physics solver. It stays
  native/vendor-facade and out of scope here.

## Verify

```sh
kbb -M:test
```
