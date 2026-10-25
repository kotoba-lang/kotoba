(ns genesis
  "kami-genesis — Genesis-compat physics backend for KAMI / e7m-sim.

  R1.x scope (ADR-2605261800 / ADR-2607010930):
    - closed-form Cartpole / DoublePendulum / N-link PlanarChain dynamics
      (RNEA + CRBA + LDL^T), semi-implicit Euler integrator
    - 6-D spatial-vector (Plucker) algebra (`genesis.spatial`)
    - GJK/EPA convex narrow-phase + OBB-SAT manifold + CCD
      (`genesis.convex`/`genesis.obb`/`genesis.ccd`)
    - DLS inverse kinematics (`genesis.ik`), joint trajectory generators
      (`genesis.trajectory`), LQR control (`genesis.lqr`), PD articulation
      control (`genesis.controllers`), and a 2-D thermal FDM PDE solver
      (`genesis.thermal`)
    - `PxScene`/`PxArticulationReducedCoordinate` (PhysX 5) and
      `isaacsim.core.api.{World, Articulation}` (Isaac Sim 4.x) API-surface
      mirrors — see `nv-compat/isaacsim` and `nv-compat/physx` for facade.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/lib.rs`
  (deleted PR #82, \"Remove Rust workspace\") as zero-dependency portable
  CLJC. Per ADR-2607010930.

  See README.md for the full per-file ported/scoped-config-only/excluded
  breakdown across all 23 original source files. In short: the closed-form
  dynamics, spatial algebra, collision geometry, IK, trajectory generation,
  LQR, thermal PDE, and PD controller modules are fully ported (pure
  math/data, no PhysX/OmniKit/wgpu dependency). The URDF-driven
  `World`/`Articulation`/`ArticulationBatch`/`IsaacWorld` facade modules
  (`genesis.world`, `genesis.batched`, `genesis.isaac-api`,
  `genesis.contact`, `genesis.mpm`, `genesis.articulation3d`) are scoped to
  config/constants-only extraction — their full numerical solver
  integration requires the (not restored) `kami_articulated` URDF-parsing
  crate. The wgpu GPU compute-dispatch modules (`wgpu_backend.rs`,
  `wgpu_planar.rs`) are excluded entirely (no CLJC representation for a
  device/queue/compute-pass binding); their WGSL kernel source strings are
  preserved as portable data in `genesis.vectorized/wgsl-source` and
  `resources/genesis/wgsl/*.wgsl`."
  )

(def adr "ADR-2605261800")
(def phase "R1.1-cartpole-poc")
(def kami-name "kami-genesis")
(def nv-compat-targets ["isaacsim.core.api" "PhysX 5"])
(def upstream-repo "Genesis-Embodied-AI/Genesis")

(def solvers ["rigid" "mpm" "sph" "fem" "pbd"])
(def solvers-implemented-r1-1 ["rigid (cartpole closed-form)"])

(defn solver-for-phase
  "Solver coverage by R1 sub-phase."
  [phase]
  (case phase
    "R1.1" "rigid"
    "R1.8" "mpm"
    nil))
