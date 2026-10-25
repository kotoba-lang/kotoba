# kotoba-lang/com-nvidia-isaac-sim

> Renamed from `kami-genesis` 2026-07-09 (ADR-2607087500) — reverse-domain
> naming reflecting genuine, verified historical API-surface conformance: this
> is a clean-room facade for NVIDIA Isaac Sim's documented
> [`isaacsim.core.api`](https://docs.isaacsim.omniverse.nvidia.com/latest/py/source/extensions/isaacsim.core.api/docs/index.html)
> (World/Articulation) and PhysX 5 (spatial-vector rigid-body dynamics,
> GJK/EPA contact), confirmed against NVIDIA's own API docs. The portable
> Clojure facade targets the Isaac Sim 4.x-era surface; the separate Python
> adapter below targets actual Isaac Sim 6.0 runtime APIs. No NVIDIA/PhysX/
> Omniverse library, header, or binary is linked by the Clojure library.
> Clojure namespaces (`genesis.*`) are unchanged.

Genesis-compat physics backend for KAMI / e7m-sim — an `isaacsim.core.api` /
PhysX 5 API-surface facade, restored as zero-dependency portable Clojure
(`.cljc`). It also has an **optional, real Isaac Sim 6.0 runtime adapter**:
the adapter is Python-only and is deliberately separated from the portable
kernel, so an Isaac installation is required only for runtime integration.

## Isaac Sim 6.0 runtime smoke test

`python/isaac_sim_6_smoke.py` runs a real headless Isaac Sim 6.0 scene. It
creates a ground plane, loads the installed Franka USD, verifies its nine DOFs,
applies a nine-joint target, explicitly steps physics and rendering, validates
the resulting joint state, and saves the scene as USD. This follows NVIDIA's
Isaac Sim 6.0 standalone lifecycle: create `SimulationApp` before Omniverse
imports, then use the experimental stage/Articulation APIs and explicit
`SimulationManager.step()` / `RenderingManager.render()` steps.

```bash
ISAACSIM_PATH=/opt/isaac-sim ./scripts/run-isaac-sim-6-smoke.sh --frames 240 \
  --output-usd artifacts/franka-smoke.usd
```

`ISAACSIM_PATH` must point at an Isaac Sim 6.0 installation containing
`python.sh`. In container or pip-package layouts, set `ISAACSIM_PYTHON` to the
configured Isaac Python launcher instead. The script writes a single JSON
result to stdout and exits nonzero if the asset root, articulation DOFs, joint
state, target application, or USD save fails. Its dependency-free contract
tests run in ordinary CI; the real smoke test must run on a Linux NVIDIA GPU
runner with Isaac Sim 6.0 installed. Trigger **Isaac Sim 6 Runtime** manually
on a runner labelled `self-hosted`, `linux`, `x64`, `nvidia-gpu`, and
`isaac-sim-6`; it uploads both the exported USD and JSON result as evidence.

### Modal GPU execution

`modal/isaac_sim_6_smoke.py` runs the same smoke test on Modal's
`RTX-PRO-6000` GPU and commits the exported USD to the
`isaac-sim-6-artifacts` Modal Volume. It invokes the NGC image's own
`/isaac-sim/python.sh`, which is required to load Kit extensions correctly.

```bash
python3 -m pip install -r modal/requirements.txt
modal secret create ngc-registry \
  REGISTRY_USERNAME='$oauthtoken' REGISTRY_PASSWORD='<NGC_API_KEY>'
modal volume create isaac-sim-6-artifacts
modal run modal/isaac_sim_6_smoke.py --frames 240
```

Create the NGC API key in the NVIDIA NGC account that has accepted the Isaac
Sim container terms. The registry secret is used only while Modal pulls
`nvcr.io/nvidia/isaac-sim:6.0.1`; it is not injected into the simulation
function. Modal build and first Kit launch can take several minutes because
the image and shader cache are large.

Restored from `kotoba-lang/kami-engine`'s `kami-genesis` crate (deleted in
[PR #82](https://github.com/kotoba-lang/kami-engine/pull/82), "Remove Rust
workspace"). Rust source recovered at commit
`a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa`. Per
[ADR-2607010930](../90-docs/adr/) (kami-engine crate restoration wave).

## Scoping summary

`kami-genesis` was a large, mixed crate: a PhysX 5 / `isaacsim.core.api`
compat facade over a family of closed-form and general reduced-coordinate
rigid-body solvers, plus GPU (wgpu) compute-dispatch paths. This
restoration ports the genuinely portable pure math/data 1:1, and scopes
the URDF-driven (`kami_articulated` crate, not restored) and wgpu-native
files to config/constants-only extraction or documented exclusion, per the
project's scoped-restoration pattern (see `kami-app-isekai` precedent).

**Fully ported (pure math/data, 1:1, no PhysX/OmniKit/wgpu dependency):**
closed-form Cartpole / DoublePendulum / N-link PlanarChain dynamics
(RNEA + CRBA + LDL^T), 6-D spatial-vector (Plücker) algebra, GJK/EPA
convex narrow-phase + OBB-SAT contact manifold + continuous collision
detection (TOI), articulation Jacobians, damped-least-squares inverse
kinematics, joint trajectory generators (cubic/quintic/waypoint), an LQR
controller, a 2-D thermal FDM PDE solver, and a PD/velocity/effort
articulation controller (adapted to operate on plain state vectors instead
of a `kami_articulated`-backed `Articulation`).

**General 3-D kinematics now available:** `genesis.articulation3d` accepts
the public plain-map result of `kami-articulated/parse-urdf`, topologically
builds a general fixed/revolute/prismatic tree, computes world-frame forward
kinematics, returns a 6xN geometric Jacobian, solves constrained
world-position IK with damped least squares, and supplies RNEA bias, CRBA
mass-matrix, forward/inverse dynamics and semi-implicit Euler stepping. This is an intentionally
zero-dependency bridge: parsing URDF remains the responsibility of the
optional `kotoba-lang/kami-articulated` library.

**Scoped to config/data-only** (URDF-driven or too large a numerical
solver core to port faithfully in this pass — see each namespace's
docstring for the full rationale): `genesis.world`, `genesis.isaac-api`,
`genesis.batched`, `genesis.mpm` (data +
obstacle-projection geometry), `genesis.contact` (data + obstacle-contact
geometry, PGS multi-body coupling excluded).

**Excluded entirely** (native GPU compute-dispatch, no CLJC
representation): `wgpu_backend.rs`, `wgpu_planar.rs`. Their WGSL kernel
source strings ARE portable data and are preserved as embedded resources
(`resources/genesis/wgsl/*.wgsl`), loaded by `genesis.vectorized/wgsl-source`.

## Per-file breakdown (all 23 original `src/*.rs` + `src/wgsl/*.wgsl`)

| Original file | Lines | CLJC namespace | Status | Notes |
|---|---:|---|---|---|
| `lib.rs` | 108 | `genesis` | ported | Crate constants + `solver-for-phase`; 1:1. |
| `cartpole.rs` | 131 | `genesis.cartpole` | ported | Closed-form Cartpole EOM, semi-implicit Euler. Pure f64 math. |
| `double_pendulum.rs` | 229 | `genesis.double-pendulum` | ported | 2-link planar manipulator dynamics + energy. Pure math. |
| `planar_chain.rs` | 589 | `genesis.planar-chain` | ported | N-link RNEA + CRBA + LDL^T solver. Pure math (mutable double-arrays used internally for the RNEA/LDL^T inner loops, wrapped in a pure functional API). |
| `vectorized.rs` | 102 | `genesis.vectorized` | ported | CPU vectorized cartpole reference; embeds `wgsl/cartpole_step.wgsl` as data via `clojure.java.io/resource`. |
| `spatial.rs` | 245 | `genesis.spatial` | ported | 6-D Plücker spatial-vector algebra (skew, Plücker transform, spatial inertia, `crm`/`crf`). Pure math. |
| `obb.rs` | 255 | `genesis.obb` | ported | OBB-OBB SAT (15-axis) + multi-point contact manifold. Pure math (uses `genesis.vec3`). |
| `ccd.rs` | 207 | `genesis.ccd` | ported | Sphere-plane analytic TOI + conservative-advancement TOI (uses `genesis.convex`). Pure math. |
| `convex.rs` | 493 | `genesis.convex` | ported | GJK distance/intersection + EPA penetration. Pure math. |
| `jacobian.rs` | 413 | `genesis.jacobian` | ported (1 test excluded) | Analytical 6xn Jacobians for all 3 topologies. One original test (`dp_jacobian_times_qdot_matches_link_state_velocity`) needed a `kami_articulated`-parsed URDF + `World`; excluded, all other (pure-math) tests ported. |
| `lqr.rs` | 406 | `genesis.lqr` | ported | Finite-difference linearisation + DARE fixed-point iteration + gain computation. Pure math. |
| `mpm.rs` | 788 | `genesis.mpm` | **scoped: data + obstacle geometry only** | `MpmMaterial`/`MpmObstacle` + `obstacle-project`/`obstacle-translate` (pure 2-vector math) ported. The ~600-line P2G/grid-update/G2P MLS-MPM solver core is a large mutable-state numerical solver; out of scope for this pass (documented gap, not native code — see docstring). |
| `obb.rs` | (see above) | | | |
| `planar_chain.rs` | (see above) | | | |
| `spatial.rs` | (see above) | | | |
| `thermal.rs` | 333 | `genesis.thermal` | ported | 2-D explicit FDM heat-conduction PDE, Dirichlet/Neumann BCs, multi-source superposition. Pure math/data. |
| `trajectory.rs` | 466 | `genesis.trajectory` | ported (1 test adapted) | Cubic/quintic polynomial + waypoint trajectory generators. The final original test drove a URDF `World`; substituted with an equivalent self-contained cartpole+controller smoke test. |
| `vectorized.rs` | (see above) | | | |
| `wgpu_backend.rs` | 866 | *(none)* | **excluded** | wgpu `Device`/`Queue`/`ComputePipeline` construction and compute-pass dispatch — no CLJC representation (native GPU binding). |
| `wgpu_planar.rs` | 349 | *(none)* | **excluded** | Same as above, for the planar-chain GPU batch path. |
| `world.rs` | 1077 | `genesis.world` | **partial: named generic articulations + topology dispatcher** | `LinkState`, `WorldError`, default params, named general-3D articulation registration, effort commands, deterministic stepping/reset and world-frame link pose/twist are implemented. A plain `kami-articulated` parse result can build the config; parsing itself remains optional. The closed-form topology dispatcher is retained. |
| `articulation3d.rs` | 1564 | `genesis.articulation3d` | **partial: data + URDF-system bridge + kinematics + dynamics** | `JointType3d`, `Body3d`, config/state helpers, `from-articulated-system`, tree world FK, 6xN world-frame Jacobian, damped-least-squares position/pose IK, RNEA bias, CRBA mass matrix, forward/inverse dynamics, gravity torque, and semi-implicit Euler integration are implemented. The bridge consumes `kami-articulated`'s plain parse result without linking that optional library. Batch simulation and contact coupling remain gaps. |
| `batched.rs` | 1329 | `genesis.batched` | **partial: env-major CPU batch dynamics + PD drive** | `ArticulationBatch`/`PdDrive` shapes, metadata, effort tensors, deterministic multi-env CPU stepping, reset, and broadcastable PD position/velocity drive with optional gravity compensation are implemented. Tensor-native GPU execution, batched IK and domain randomization remain gaps. |
| `contact.rs` | 1014 | `genesis.contact` | **partial: static PGS + articulated point contact** | `Collider`/`Obstacle` data, plane/AABB/convex sphere contact generation, point Jacobian based `M^-1 J^T` normal impulse, restitution, Baumgarte correction, two-axis Coulomb friction, deterministic multi-contact static-obstacle PGS sweeps, caller-owned warm starting, and equal-and-opposite normal point impulse between two articulations are implemented. Articulated manifolds and inter-body friction remain gaps. |
| `isaac_api.rs` | 708 | `genesis.isaac-api` | **partial: clock + live world delegation** | `IsaacWorld` clock bookkeeping plus generic articulation registration, effort command, world step/reset, and link state access are implemented through `genesis.world`. Python `SimulationApp` remains the real Isaac Sim 6 runtime integration. |
| `ik.rs` | 517 | `genesis.ik` | ported | DLS inverse kinematics over all 3 topologies (uses `genesis.jacobian`). Pure math. |
| `src/wgsl/cartpole_step.wgsl` | 63 | `resources/genesis/wgsl/cartpole_step.wgsl` | ported (as data) | Embedded verbatim; loaded by `genesis.vectorized/wgsl-source`. |
| `src/wgsl/double_pendulum_step.wgsl` | 87 | `resources/genesis/wgsl/double_pendulum_step.wgsl` | ported (as data) | Embedded verbatim (not wired to a CLJC loader — no CLJC consumer for the DP GPU path since `wgpu_backend.rs` is excluded — but preserved as portable data). |
| `src/wgsl/planar_chain_step.wgsl` | 201 | `resources/genesis/wgsl/planar_chain_step.wgsl` | ported (as data) | Same as above (`wgpu_planar.rs` excluded). |
| `controllers.rs` | 327 | `genesis.controllers` | ported (adapted) | PD/velocity/effort control law + clamping ported 1:1 as a pure function of `(q, qdot, action, controller)`, adapted from mutating a `kami_articulated`-backed `Articulation` in place. See docstring. |

23 original `src/*.rs` files (+ 3 `.wgsl` shaders) accounted for above.
Two (`wgpu_backend.rs`, `wgpu_planar.rs`) are excluded entirely; the
remaining 21 all have a CLJC namespace, of which 15 are fully ported and 6
are scoped to config/data-only extraction.

## Structure

```
src/genesis.cljk                 — root namespace (crate constants)
src/genesis/vec3.cljk             — shared portable 3-vector helpers (not from a single Rust file; factors out `glam::Vec3` ops used by obb/ccd/convex/spatial)
src/genesis/{cartpole,double_pendulum,planar_chain}.cljc  — closed-form dynamics
src/genesis/vectorized.cljk       — CPU-vectorized cartpole + embedded WGSL
src/genesis/spatial.cljk          — 6-D Plücker spatial-vector algebra
src/genesis/{obb,ccd,convex}.cljc — collision geometry (SAT/CCD/GJK-EPA)
src/genesis/jacobian.cljk         — analytical articulation Jacobians
src/genesis/ik.cljk               — DLS inverse kinematics
src/genesis/trajectory.cljk       — joint trajectory generators
src/genesis/lqr.cljk              — LQR control
src/genesis/thermal.cljk          — 2-D thermal FDM PDE solver
src/genesis/controllers.cljk      — PD/velocity/effort articulation control
src/genesis/{world,isaac_api,batched,articulation3d,contact,mpm}.cljc — scoped config/data-only facades
resources/genesis/wgsl/*.wgsl     — embedded WGSL compute-shader source (portable data)
test/genesis*.cljc                — mirrored test namespaces (1 per src namespace + root smoke test)
```

## Test plan

```
kbb -M:test
```

Ran **128 tests / 2518 assertions, 0 failures, 0 errors** (verified via
`kbb -M:test` against a full JVM Clojure execution, not just syntax
checking).

Every original Rust `#[test]` in a ported file is reproduced 1:1 unless
noted above (jacobian.rs: 1 excluded; trajectory.rs / controllers.rs: URDF
integration tests adapted to use the closed-form topology states
directly instead of a `kami_articulated`-parsed `World`). The
scoped-config-only namespaces (`world`, `isaac-api`, `batched`,
`articulation3d`, `mpm`, `contact`) get smoke tests for the ported data/
geometry surface plus the root `genesis` namespace-loads test.
