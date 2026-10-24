(ns kami-app-giemon
  "kami-app-giemon — Giemon robot kit viewer (giemon.etzhayyim.com).

  Restored (scoped) from the legacy `kami-app-giemon` Rust crate
  (`kotoba-lang/kami-engine`, 2 files (`lib.rs` + `mold_field.rs`), deleted
  in PR #82 \"Remove Rust workspace\") as zero-dependency portable CLJC, per
  ADR-2607010930 (`com-junkawasaki/root`).

  The original crate was 4 `wasm-bindgen` viewer entry points
  (`run_giemon_v1`/`run_giemon_sim_v1`/`run_giemon_kabitori_sim_v1`/
  `run_giemon_otete_sim_v1`/`run_giemon_hitogata_v1`/
  `run_giemon_caterpillar_v1`) orchestrating `KamiApp`/`CadSceneAdapter`
  GPU scene-graph builds, plus (for the physics-arm/kabitori/otete demos)
  URDF-loaded kami-genesis 3-D rigid-body articulations driven by a
  Featherstone-class spatial solver + contact solver, an orbit camera, and
  pick-to-highlight input handling — all native WASM/wgpu substrate with
  no meaningful portable representation as a whole program.

  Rather than attempt a 1:1 port of that (which would carry no
  computational value without the native GPU/solver state it operates
  on), this restoration extracts the genuinely portable computational
  kernels:

  | Namespace | From | Purpose |
  |---|---|---|
  | `kami-app-giemon.geom` | `lib.rs` (`segment_box`, `push_box`/`push_cyl`) | vec3/quaternion/transform math kernel (portable subset of `glam`) |
  | `kami-app-giemon.armcrawler` | `lib.rs` (`crawler_chassis`/`arm_assembly`/`build_armcrawler`) | ArmCrawler chassis + 6-DOF display-pose arm + gripper procedural geometry |
  | `kami-app-giemon.hitogata` | `lib.rs` (`hitogata_legs`/`hitogata_torso`/`hitogata_arms`/`build_hitogata`) | Giemon Bipede humanoid procedural geometry |
  | `kami-app-giemon.caterpillar` | `lib.rs` (`caterpillar_body`/`caterpillar_sensors`/`build_caterpillar`) | Giemon Caterpillar tracked-UGV procedural geometry |
  | `kami-app-giemon.mold-field` | `mold_field.rs` (`MoldField`) | scrubbable 2-D mold-coverage grid |
  | `kami-app-giemon.kabitori` | `lib.rs` (kabitori brush constants + contact-point selection) | brush-tip contact-point geometry + scrub-intensity formula |

  **Excluded entirely** (native-only, no portable logic): the
  `wasm-bindgen` entry points, `KamiApp`/`CadSceneAdapter`/`RenderContext`
  GPU scene-graph building, the orbit camera + pick-to-highlight input
  handling, URDF loading (`kami_articulated::parse_urdf`), and the
  kami-genesis 3-D rigid-body spatial + contact solver (forward
  kinematics, RNEA/CRBA dynamics, contact stepping, the point-Jacobian
  tangential-velocity computation) — same class of scoping decision as
  `kotoba-lang/kami-app-isekai`."
  (:require [kami-app-giemon.geom]
            [kami-app-giemon.armcrawler]
            [kami-app-giemon.hitogata]
            [kami-app-giemon.caterpillar]
            [kami-app-giemon.mold-field]
            [kami-app-giemon.kabitori]))
