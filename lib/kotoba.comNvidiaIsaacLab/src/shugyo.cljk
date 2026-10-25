(ns shugyo
  "kami-shugyo (修行) — Isaac Lab-equivalent RL training framework. Restored
  from the deleted `kami-shugyo` Rust crate (`kotoba-lang/kami-engine`,
  removed in PR #82 \"Remove Rust workspace\") as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root). Zero-dep portable CLJC —
  every submodule below runs unchanged on JVM / SCI / ClojureScript.

  Dependency relationships found while restoring the original `Cargo.toml`:
    - `kami-articulated` (path dep, `parse_urdf`) — a REAL dependency of the
      original crate, but its own restoration (`kotoba-lang/kami-articulated`)
      is empty (mid-restoration, parallel work) — duck-typed here instead of
      waited on: `shugyo.reach` ships its own minimal regex-based URDF-XML
      chain extractor.
    - `kami-genesis` (physics engine: `World`, `ArticulationBatch`,
      `step_vectorized`, IK solver) — NEVER restored as a kotoba-lang repo —
      duck-typed: `shugyo.cartpole` reimplements the classic cart-pole ODE
      (generalized to a `CartpoleConfig`, matching `kotoba-lang/
      cartpole-wasm`'s sibling restoration), and `shugyo.reach` reimplements
      generic serial-chain forward kinematics + computed-torque / lumped-
      gravity dynamics + finite-difference damped-least-squares IK.
    - `kami-sensor-sim` (`ContactSensor`) — NEVER restored as a kotoba-lang
      repo — duck-typed: `shugyo.ee-reach/ee-in-contact?` reimplements the
      point-goal proximity sensor the original tests actually exercised.

  Every duck-typed substitution reimplements the *real computational content*
  the missing dependency would have provided (classic ODEs / real forward
  kinematics / a real proximity sensor / real numeric IK) — never a stub —
  and is documented in the consuming namespace's own docstring.

  Submodules (require directly rather than through this root namespace; this
  mirrors the convention used elsewhere in kotoba-lang, e.g. `kudaki-clj` /
  `nagare`, where `src/<lib>/*.cljc` are required individually and there is
  no aggregating re-export barrel):
    `shugyo.lcg`        — shared deterministic LCG (u64-faithful on JVM,
                           `goog.math.Long`-backed on CLJS).
    `shugyo.traits`      — `RLEnv` / `VecRLEnv` protocols, `StepResult`,
                           `run-zero-action-rollout`.
    `shugyo.dr`          — `Range`, `DomainRandomizationCfg`
                           (`dr-around`/`dr-identity`/`dr-sample`/
                           `dr-sample-n`) + the duck-typed `CartpoleConfig`
                           shape.
    `shugyo.scene-cfg`   — Isaac Lab-compat scene config (scene.yaml -> EDN
                           substitution) + the embedded Cartpole scene fixture.
    `shugyo.cartpole`    — `CartpoleEnv` (`RLEnv`) + `VectorizedCartpoleEnv`
                           (`VecRLEnv`), classic cart-pole ODE.
    `shugyo.policy`      — `LinearPolicy`, `act-batch`, `rescale-to-limits`,
                           `evaluate`, `random-search` (ARS-lite trainer).
    `shugyo.reach`       — `VectorizedReachEnv` (`VecRLEnv`): duck-typed URDF
                           chain parsing, forward kinematics, computed-torque
                           / lumped-gravity dynamics, physics DR.
    `shugyo.ee-reach`    — `VectorizedEeReachEnv` (`VecRLEnv`): Cartesian
                           end-effector reach, duck-typed contact sensor,
                           finite-difference damped-least-squares IK.

  Excluded from this restoration: the original crate's `examples/*.rs` (3
  files) — thin CLI/bench harnesses over the library with no unique
  computational content beyond what the 8 submodules above already port; see
  README.md."
  (:require [shugyo.cartpole]
            [shugyo.dr]
            [shugyo.ee-reach]
            [shugyo.lcg]
            [shugyo.policy]
            [shugyo.reach]
            [shugyo.scene-cfg]
            [shugyo.traits]))

(def adr "ADR-2607010930")
(def kami-name "e7m-shugyo")
(def nv-compat-target "isaaclab.envs.ManagerBasedRLEnv")
