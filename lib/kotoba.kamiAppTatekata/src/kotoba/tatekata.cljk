(ns kotoba.tatekata
  "kotoba.tatekata — 建方: the material-process + robot-op-sequence math for
  robotic construction, ported from `kami-app-tatekata` (kami-engine, Rust,
  retired per ADR-2607010000-kotoba-runtime-sdk-cljc-migration).

  This is a parent overview namespace only; the actual contract lives in the
  child namespaces below. No network, no I/O, portable `.cljc` across
  JVM / ClojureScript / SCI / GraalVM.

  - `kotoba.tatekata.deposit-field` — concrete-deposition / screed-levelling
    height field (`robot:printer` steps: foundation slab, epoxy floor,
    paving). An application-layer coverage-progress model, not a granular/MPM
    concrete rheology solver.
  - `kotoba.tatekata.thermal` — a genuine 2-D transient heat-conduction PDE
    (explicit FDM, CFL-bounded), ported from `kami-genesis::ThermalField`.
    Not a stand-in: this is real continuum heat transfer with a travelling
    Gaussian source and Dirichlet/Neumann boundary conditions.
  - `kotoba.tatekata.weld-field` — moving heat-source weld-pass model
    (`robot:bolter` steps: steel column erection, roof trusses) built on
    `kotoba.tatekata.thermal`.
  - `kotoba.tatekata.process` — the robot operation-sequence timeline per
    construction step (procure → deliver → stage → build → fasten →
    inspect): pure `StepPlan` derivation and lookup functions. The real
    upstream `process.json` data source is unavailable in this monorepo
    checkout (see that namespace's docstring); this repo ships only a small
    synthetic EDN fixture for test coverage.

  Unported (stays Rust+wgpu host adapter in `kami-engine`, out of this
  library's scope): the `#[cfg(target_family = \"wasm\")]` viewer/app glue in
  `kami-app-tatekata::lib.rs` (`run_tatekata_v1`, the HUD status bridge,
  `ArmCell` render/animation, the `Agv` cart/payload floating-base physics),
  and the separate `kami-app-giemon-factory` crate it depends on
  (`Factory`/`ConstructionOrder`/`Robots`/`static_boxes`/`arm6_config` — a
  different crate, out of scope for this port). The rigid-body/articulation
  contact solver (`kami_articulated`, `Articulation3dConfig`, `ContactWorld`)
  is not ported anywhere in kotoba-lang yet.")
