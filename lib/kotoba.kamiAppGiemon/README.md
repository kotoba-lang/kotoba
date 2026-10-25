# kotoba-lang/kami-app-giemon

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-app-giemon`
Rust crate (2 files, `lib.rs`/`mold_field.rs`, deleted in kotoba-lang/kami-engine
PR #82 "Remove Rust workspace from kami-engine") as part of the **clj-wgsl
migration** (ADR-2607010930, `com-junkawasaki/root`).

## What this is

The original crate ("Giemon robot kit viewer", giemon.etzhayyim.com) was 6
`wasm-bindgen` viewer entry points (`run_giemon_v1`/`run_giemon_sim_v1`/
`run_giemon_kabitori_sim_v1`/`run_giemon_otete_sim_v1`/`run_giemon_hitogata_v1`/
`run_giemon_caterpillar_v1`) orchestrating `KamiApp`/`CadSceneAdapter` GPU
scene-graph builds, plus (for the physics-arm/kabitori/otete demos) URDF-loaded
kami-genesis 3-D rigid-body articulations driven by a Featherstone-class spatial
solver + contact solver, an orbit camera, and pick-to-highlight input handling —
all native WASM/wgpu substrate with no meaningful portable representation as a
whole program.

Rather than attempt a 1:1 tick-loop port (which would carry no computational
value without the native GPU/solver state it operates on), this restoration
extracts the genuinely **portable computational kernels**: the procedural
geometry generation for the 3 static display-pose models (each part's
scale/rotation/translation, given the model's fixed pose parameters), and the
`MoldField` scrubbable-coverage grid.

| Namespace | From | Purpose |
|---|---|---|
| `kami-app-giemon.geom` | `lib.rs` (`segment_box`, `push_box`/`push_cyl`) | vec3/quaternion/transform math kernel — portable subset of `glam` (`Vec3`/`Quat`/`Mat4::from_scale_rotation_translation`/`Quat::from_rotation_arc`) |
| `kami-app-giemon.armcrawler` | `lib.rs` (`crawler_chassis`/`arm_assembly`/`build_armcrawler`) | ArmCrawler: rubber-track crawler chassis (2 tracks + 8 drive wheels) + 6-DOF display-pose arm (J1-J6) + gripper |
| `kami-app-giemon.hitogata` | `lib.rs` (`hitogata_legs`/`hitogata_torso`/`hitogata_arms`/`build_hitogata`) | Giemon Bipede: 17-DOF humanoid standing display pose |
| `kami-app-giemon.caterpillar` | `lib.rs` (`caterpillar_body`/`caterpillar_sensors`/`build_caterpillar`) | Giemon Caterpillar: dual-track UGV, 6 drive wheels/side + LiDAR/stereo sensors |
| `kami-app-giemon.mold-field` | `mold_field.rs` (`MoldField`) | scrubbable 2-D mold-coverage grid (circular-footprint erosion) |
| `kami-app-giemon.kabitori` | `lib.rs` (kabitori brush constants + contact-point selection from `kabitori_scrub_step`) | brush bristle-tip contact-point geometry + scrub-intensity formula |

Each model namespace emits parts as plain maps `{:id :name :color :scale
:translate :rotation}` — the pure geometry data the original `push_box`/
`push_cyl` calls fed into the native `CadSceneAdapter`. `kami-app-giemon.geom`
provides `transform`/`transform-point` so this data can be verified against a
world-space point, same as the original `Mat4`.

**Excluded entirely** (native-only, no portable logic): the `wasm-bindgen`
entry points, `KamiApp`/`CadSceneAdapter`/`RenderContext` GPU scene-graph
building, the orbit camera + pick-to-highlight input handling, URDF loading
(`kami_articulated::parse_urdf`), and the kami-genesis 3-D rigid-body spatial +
contact solver (forward kinematics, RNEA/CRBA dynamics, contact stepping, the
point-Jacobian tangential-velocity computation) — same class of scoping
decision as `kotoba-lang/kami-app-isekai`.

## Status

Restored (scoped) — 34 tests / 455 assertions, 0 failures. The original had 8
`#[test]`s (`mold_field.rs`'s 2 tests ported 1:1; `lib.rs`'s 6 tests all
exercised the native URDF/solver path and are not portable) — these provide
coverage of the ported geometry/mold-field kernels instead.

## Develop

```bash
kbb -M:test
```
