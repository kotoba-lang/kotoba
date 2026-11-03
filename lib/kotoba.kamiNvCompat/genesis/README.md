# kami-genesis

Genesis physics backend bind — Isaac Sim articulation API-compat target.

**Status**: R1.x active — KAMI-native reduced-coordinate solver implemented
(the Genesis-Python/Taichi bind in the diagram below is still reserved). The
`isaacsim.core.api`-shaped surface runs application code today against the
native solver; see "Implemented surface" below for what is real vs reserved.
**Upstream**: Genesis-Embodied-AI/Genesis (Apache-2.0).
**Fork policy**: upstream-only (no religious-corp fork per §D8).

## Implemented surface (R1.x actual, KAMI-native solver)

Clean-room `isaacsim.core.api` mirror (`isaac_api.rs`) — no NVIDIA library
linked; all dynamics solved by the native reduced-coordinate solvers in
`world` / `planar_chain` / `articulation3d` / `cartpole`.

| Isaac Sim 4.x surface | kami-genesis | Notes |
|---|---|---|
| `World(physics_dt)` / `reset` / `step(render=False)` | `IsaacWorld` | single-env (num_envs=1) |
| `world.{current_time, current_time_step_index, get_physics_dt}` | ✅ | clock rewinds on `reset()` |
| `Articulation.get_joint_positions` / `get_joint_velocities` / `num_dof` | `ArticulationView` | `[n_dof]` (Isaac: `[num_envs, n_dof]`) |
| `Articulation.dof_names` / `get_dof_index(name)` | `ArticulationView` | ordered actuated-joint names; name→DOF index |
| `Articulation.get_dof_limits()` | `ArticulationView` + `ArticulationBatch` | per-DOF `[lower, upper]` from URDF — RL action rescaling / obs normalisation |
| `Articulation.set_joint_efforts` (~`apply_action`) | `ArticulationViewMut` | torque/force per DOF |
| `Articulation.set_joint_positions` / `set_joint_velocities` | `ArticulationViewMut` | seed/teleport; RL reset-to-distribution |
| `Articulation.get_jacobians` | `get_jacobian(link)` | `[6, n_dof]` per link |
| `RigidPrimView.get_world_poses(link)` | `get_world_pose(link)` | `(pos[3], quat_wxyz[4])` |
| `RigidPrimView.get_velocities(link)` | `get_world_velocity(link)` | `(linear[3], angular[3])` world-frame — feeds downstream sensors (IMU) |
| `articulation.get_articulation_controller()` | `ArticulationControllerView` | PD position/velocity + feedforward-effort drive, `set_gains` / `set_max_efforts`, effort clamp; **drive gains/limits auto-seeded from URDF** (`<limit effort>` → max_efforts, `<dynamics damping>` → kd) |
| **Multi-env** `Articulation(prim_paths_expr="…/env_.*/Robot")` view | `ArticulationBatch` | `[num_envs, n_dof]` tensor I/O (`get/set_joint_{positions,velocities,efforts}`, `step`, `reset`), built from URDF via `from_urdf(sys, gravity, dt, num_envs)`; `dof_names` / `get_dof_index` (joint names aligned to DOF order); **per-env physics domain randomization** (`randomize_physics` / `randomize_gravity` / `randomize_mass` — per-env gravity scale + body mass/inertia scale; only the dynamics path varies per env, kinematics stays shared); `set_joint_position_targets` (implicit-PD, global or per-joint `(kp, kd)` gains, recomputed per step, effort-clamped, optional **gravity-compensation** feedforward via `set_gravity_compensation`), `set_joint_velocity_targets` (implicit velocity actuator), `set_joint_position_velocity_targets` (combined pos+vel-feedforward actuator) and `set_joint_trajectory_targets` (full pos+vel+**accel** feedforward → near-exact computed-torque trajectory tracking) — the effort / position / velocity actuator trio, plus a **computed-torque** (feedback-linearizing inverse-dynamics) mode via `set_computed_torque_control`; per-env `get_jacobians(link)` → `[num_envs,6,n_dof]` + `get_world_poses(link)` → `([num_envs,3],[num_envs,4])` + `get_applied_joint_efforts()` (last-step torques) + `solve_ik(link, targets)` / `solve_ik_point(link, tool_offset, targets)` (per-env position IK) + `solve_ik_pose(link, pos, quat)` (full 6-DOF **pose** IK — position + orientation, DLS on the 6×n Jacobian, Isaac differential IK); Spatial3d (Featherstone) solver, bit-identical to the single-env loop per env |

Topologies routed natively: Cartpole (closed-form), DoublePendulum, N-link
PlanarChain (RNEA+CRBA+LDLᵀ), and a general Spatial3d Featherstone fallback
(e.g. the 6-DOF giemon arm). GPU-batched 1024-env paths (`vectorized` /
`WgpuBackend`) are validated bit-identical to the scalar loop with ≥10×
speedup (`r1_2_scorecard`).

**Partial**: multi-env `[num_envs, n_dof]` lives in a dedicated
`ArticulationBatch` view (CPU loop today; GPU-batched paths exist in
`vectorized` / `WgpuBackend`), built from a URDF and restricted to the Spatial3d
solver — it is a separate object from the single-env `IsaacWorld`, not yet a
unified `World.add_articulation(num_envs=…)`. The batch view now carries the
full RL-loop surface — `dof_names` / `get_dof_index`, per-env `get_jacobians` /
`get_world_poses`, and an implicit-PD `set_joint_position_targets` actuator with
global or per-joint gains. Remaining: GPU-parallel execution of the general
batch (today a CPU loop), and unification with the single-env `World`.

**Not yet covered** (honest): a single `World` that holds both single- and
multi-env articulations; PD **stiffness** (`kp`) auto-load (no standard URDF
field — needs the USD drive `stiffness`, so `kp` stays 0 until `set_gains`); the
full Genesis 5-solver Taichi→wgpu bind below.

A full vectorized Isaac Lab RL loop (reset → per-env sampled state → gravity-
comped implicit-PD reach policy → step → joint/pose/Jacobian observations) runs
end-to-end as a documentation-as-test in
`tests/isaac_lab_rl_loop.rs` — the canonical usage example for the batch view.
`tests/pose_control.rs` closes the operational-space loop: `solve_ik_pose` →
computed-torque drive holds a full 6-DOF end-effector pose under gravity.
`tests/trajectory_tracking.rs` chains the documented IK → `WaypointTrajectory`
pipeline: pose-IK-validated joint waypoints, sampled and run through FK, trace a
Cartesian pose path through each waypoint, and computed-torque-track a smooth
move on the 6-DOF arm near-exactly.

**Solver invariants** (regression-tested on the real 6-DOF giemon arm6 URDF, not
just hand-built configs):
- `inverse_dynamics` is the *exact* inverse of `forward_dynamics` — including the
  joint viscous-damping torque (a fix that made computed-torque tracking
  near-exact on damped URDF arms).
- the CRBA mass matrix `M(q)` is symmetric positive-definite at every config.
- total kinetic energy is conserved (no secular drift) coasting in zero gravity.
- the contact solver uses **split impulse**: penetration push-out is a separate
  position-only pseudo-velocity pass, so the Baumgarte correction injects no
  kinetic energy and a deeply-penetrated body is eased out without launching
  (the residual ≈10% gain on a fully-elastic bounce is semi-implicit-Euler
  velocity-reversal timing, not the contact bias).

See `90-docs/adr/0033-kami-genesis-isaacsim-core-api-surface.md` for the
clean-room provenance and surface-maturation record.

## Why Genesis (vs MuJoCo MJX)

Genesis ships 5 solvers in a single backend (rigid / MPM / SPH / FEM / PBD).
MJX is rigid-only, requiring 4 additional backend integrations.

## Integration path (R1.1+)

```
Python user code (Isaac Sim API-compat)
  → pymagatama.nv_compat.isaacsim.core.api.World
    → kami-genesis bind
      → Genesis Python API
        → Taichi IR
          → Vulkan SPIR-V
            → wgpu compute pipeline (WebGPU)
              → KAMI scene render
```

**CPU fallback**: Taichi `cpu` backend → WASM (Emscripten) for browser without WebGPU.

## R1.1 PoC plan (Cartpole)

1. Vendor Genesis @ `lib/genesis/` (charter-rider-applicator skip pattern)
2. Write minimal Rust → Python bridge (PyO3 or wasm-bindgen + Pyodide)
3. Load Cartpole URDF from `fixtures/cartpole/cartpole.urdf`
4. Run PPO training for 1000 episodes
5. Compare reward curve vs Isaac Sim baseline (target: ±10%)

## Known gaps (honest scoring)

| Gap | R1.1 impact |
|---|---|
| Genesis WebGPU backend non-existent upstream | Need to contribute. R1.1 may need CPU-only first. |
| Taichi → wgpu transpile is research-grade | Wave-1: only rigid solver, deferred MPM/SPH/FEM/PBD to R1.8 |
| Python-in-WASM (Pyodide) startup ~3-5s | Mitigation: pre-warm in Worker before user interaction |

## License

Apache 2.0 + Charter Compliance Rider v2.0.
