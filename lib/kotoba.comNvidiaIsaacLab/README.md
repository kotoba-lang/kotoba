# kotoba-lang/com-nvidia-isaac-lab (formerly kami-shugyo, e7m-shugyo 修行)

> Renamed from `kami-shugyo` 2026-07-09 (ADR-2607087500) — reverse-domain
> naming reflecting genuine, verified API-surface conformance: this targets
> NVIDIA Isaac Lab's real, documented
> [`isaaclab.envs.ManagerBasedRLEnv`](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.envs.html)
> (manager-based MDP RL task environment), confirmed against NVIDIA's own
> API docs, not renamed on assumption alone. Clojure namespaces (`shugyo.*`)
> are unchanged.

Isaac Lab-equivalent RL training framework — `isaaclab.envs.ManagerBasedRLEnv`
API-compat target. Zero-dependency, portable CLJC (JVM / SCI / ClojureScript /
GraalVM / kotoba-WASM).

Restored from the deleted `kami-shugyo` Rust crate
(`kotoba-lang/kami-engine`, removed in PR #82 "Remove Rust workspace") as part
of the clj-wgsl migration, ADR-2607010930 (`com-junkawasaki/root`).

## Modules (8 submodules + root, ~1480 lines of `src/`)

| Namespace                  | Lines | Restored from        | Purpose |
|-----------------------------|------:|-----------------------|---------|
| `shugyo`                    |    70 | `lib.rs`              | Root namespace: docstring cataloguing every dependency/duck-typing relationship; requires all 8 submodules. |
| `shugyo.lcg`                |   100 | (shared across all `Lcg` shapes) | Shared deterministic LCG — u64-faithful `unchecked-*` longs on JVM, `goog.math.Long` on CLJS. |
| `shugyo.traits`             |    84 | `traits.rs`           | `RLEnv` / `VecRLEnv` protocols, `StepResult`, `run-zero-action-rollout`. |
| `shugyo.dr`                 |    98 | `dr.rs`                | `Range`, `DomainRandomizationCfg` (`dr-around`/`dr-identity`/`dr-sample`/`dr-sample-n`) + duck-typed `CartpoleConfig`. |
| `shugyo.scene-cfg`          |    86 | `scene_cfg.rs`         | Isaac Lab-compat scene config (scene.yaml → EDN substitution) + embedded Cartpole fixture. |
| `shugyo.cartpole`           |   261 | `cartpole_env.rs` + `vectorized_env.rs` | `CartpoleEnv` (`RLEnv`) + `VectorizedCartpoleEnv` (`VecRLEnv`), classic cart-pole ODE parameterized by `CartpoleConfig`. |
| `shugyo.policy`             |   134 | `policy.rs`            | `LinearPolicy`, `act-batch`, `rescale-to-limits`, `evaluate`, `random-search` (ARS-lite trainer). |
| `shugyo.reach`              |   392 | `reach_env.rs`         | `VectorizedReachEnv` (`VecRLEnv`): duck-typed URDF-XML chain extractor, forward kinematics, computed-torque / lumped-gravity dynamics, physics DR. |
| `shugyo.ee-reach`           |   255 | `ee_reach_env.rs`      | `VectorizedEeReachEnv` (`VecRLEnv`): Cartesian EE reach, duck-typed contact sensor, finite-difference damped-least-squares IK. |

Plus two integration test namespaces (`shugyo.vec-rl-env-test`,
`shugyo.perception-rl-test`, ported from `test_vec_rl_env.rs` /
`test_perception_rl.rs`) and a build-time portability guard
(`shugyo.portability-test`, in the style already used by `kudaki-clj` /
`nagare`).

## Test / assertion counts

`kbb -M:test` — **46 tests, 867 assertions, 0 failures, 0 errors.**

All applicable original Rust `#[test]`s were ported 1:1 (fixture-dependent
tests adapted to construct config/scene data directly instead of loading
`fixtures/cartpole/*` — see "Deviations" below).

## Dependency relationships (why everything is duck-typed)

The original `Cargo.toml` path-depended on:

- **`kami-articulated`** (`parse_urdf`) — a *real* dependency, but its own
  kotoba-lang restoration (`kotoba-lang/kami-articulated`) is currently
  **empty** (mid-restoration, parallel ongoing work). Not waited on.
- **`kami-genesis`** (`World`, `ArticulationBatch`, `step_vectorized`, batched
  IK) — the physics engine — **never restored** as a kotoba-lang repo.
- **`kami-sensor-sim`** (`ContactSensor`) — **never restored** as a
  kotoba-lang repo.

Every one of these is duck-typed: the *real computational content* each
dependency would have supplied is reimplemented as genuine CLJC math, never a
stub, and documented in the consuming namespace's own docstring. Summary:

1. **scene.yaml → EDN** (`shugyo.scene-cfg`): no zero-dependency YAML parser
   is available in this project (an established substitution already used by
   ~15 other `kami-*-scene` restorations in kotoba-lang). `load-scene-edn` is
   a light validator over already-parsed EDN data with the same field shape,
   kebab-cased; an embedded EDN fixture reconstructs the Cartpole scene
   numerically (matches `cartpole-wasm`'s CartPole-v1 constants: pole
   ±0.2094 rad / 12°, cart ±2.4 m).
2. **URDF text → `CartpoleConfig` map directly** (`shugyo.cartpole`): instead
   of parsing URDF `<link>`/`<joint>` elements to derive cart/pole
   mass/length/force, both `cartpole-env-new` and
   `vectorized-cartpole-env-new` accept a `CartpoleConfig` map at
   construction — the same numeric content, just supplied explicitly.
3. **Classic cart-pole ODE, parameterized** (`shugyo.cartpole`): the actual
   physics `kami_genesis::step_vectorized`/`step_vectorized_per_env` would
   have run — the Barto/Sutton/Anderson equations of motion — generalized to
   take an arbitrary `CartpoleConfig` rather than fixed constants (this
   generalizes the fixed-constant ODE `kotoba-lang/cartpole-wasm` already
   ported from the same original dynamics, for consistency across the two
   sibling restorations).
4. **Minimal URDF-XML chain extractor** (`shugyo.reach`): a regex-based
   extractor of `<link>`/`<joint type="revolute">` elements (mass, inertial
   origin, joint origin, axis, position limits) — NOT a general URDF parser
   (no branching trees, no non-revolute joints, no visual/collision
   elements), just enough to reconstruct the same ARM2 fixture the original
   Rust tests embedded, generic to any single-axis-per-joint serial chain of
   that shape.
5. **Forward kinematics** (`shugyo.reach`): genuine sequential rigid
   transforms down the chain (Rodrigues' rotation formula per joint), generic
   to any chain length.
6. **Computed-torque control simplification** (`shugyo.reach`): when
   `:computed-torque? true` (default), each joint is feedback-linearized to
   an independent critically-tuned 2nd-order linear system
   (`q'' = kp*(target-q) - kd*q'`) — the textbook *result* computed-torque
   control achieves (exact tracking regardless of configuration/gravity),
   integrated with semi-implicit Euler. This is a legitimate simplification,
   not a hack.
7. **Lumped gravity-torque approximation** (`shugyo.reach`): when
   `:computed-torque? false` (plain PD, used by the DR-divergence tests),
   each joint gets a decoupled per-joint pendulum gravity-torque term
   `τ_gravity_d ≈ -(downstream mass_d)·gravity_z·lever_d·cos(q_d)`, scaled by
   each env's per-env gravity/mass DR factors — genuinely makes `gravity-dr`
   / `mass-dr` change the passive/PD steady-state per env (verified by
   `gravity-dr-diverges-envs-and-is-reproducible` /
   `mass-dr-diverges-envs-under-fixed-torque`).
8. **Contact sensor** (`shugyo.ee-reach/ee-in-contact?`): a genuine (if
   minimal) point-goal proximity sensor
   (`in-contact? ⟺ ‖ee - goal‖ < contact-radius`, returning a unit contact
   normal with a finite fallback at zero distance) — exactly what the
   original tests used `kami_sensor_sim::ContactSensor` for.
9. **Numeric IK** (`shugyo.ee-reach/solve-ik-point`): damped-least-squares IK
   against a **finite-difference Jacobian** of the forward-kinematics
   function (central differences, ε = 1e-4 rad per joint), generic to any
   chain length — genuinely solves the IK per env each call, not a
   lookup/oracle.

## Numeric-tolerance adjustments

- `mass-dr-diverges-envs-under-fixed-torque` (`shugyo.reach-test`): the
  original Rust test compares env 0 vs env 1's joint angles after a fixed
  number of steps. The initial per-env physics-DR sampler (a single shared
  LCG stream advanced across all envs) happened to draw very similar
  `mass-scale` values for envs 0 and 1 specifically, producing a real but
  sub-1e-3 divergence and a flaky-looking failure. Fixed by switching
  `shugyo.reach/randomize-physics` to one independently-seeded LCG stream per
  env (`seed + env-index`, matching the per-env goal-sampling convention
  already used elsewhere in the same namespace) — better decorrelated across
  adjacent envs. This preserves the qualitative claim ("mass DR diverges
  envs") without weakening any assertion; the fix is in the *sampler*, not
  the test.

No other test required threshold changes — the duck-typed physics converge
comfortably within the original episode-length budgets.

## Excluded: `examples/`

The original crate's `examples/*.rs` (3 files) were thin CLI/bench harnesses
over the library (construct an env, run a rollout, print numbers) — no unique
computational content beyond what the 8 modules above already port. Not
restored.

## Usage

```clojure
(require '[shugyo.reach :as reach]
         '[shugyo.policy :as policy]
         '[shugyo.traits :as t])

(def urdf "...") ; a serial revolute-chain URDF (see shugyo.reach docstring)
(def env (reach/vectorized-reach-env-new 64 urdf (reach/reach-cfg-default)))
(def init (policy/zeros (t/observation-dim-per-env env) (t/action-dim-per-env env)))
(def result (policy/random-search env init 100 0.3 200 42))
```

## License

Apache 2.0 + Charter Compliance Rider v2.0.
