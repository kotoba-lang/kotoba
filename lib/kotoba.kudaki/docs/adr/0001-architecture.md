# ADR-0001 — kudaki-clj architecture: a pure-`.cljc` explicit FEA kernel

- Status: Accepted
- Date: 2026-06-27
- Context tags: solver, structural-dynamics, LS-DYNA-class, portable-cljc

## Decision

Build an LS-DYNA-class **explicit nonlinear structural dynamics** solver as a
zero-third-party-dependency `.cljc` library, so the *same* kernel runs on the JVM, SCI,
ClojureScript, GraalVM and kotoba-clj (WASM). The design actor injects it as a port to
*verify* crashworthiness; there is no native solver, no FFI, no license server.

## Why explicit, and why pure Clojure

- **Explicit central difference** needs no global stiffness assembly and no linear
  solve per step (lumped diagonal mass → `a = M⁻¹(F_ext − F_int)`). The whole solver is
  therefore expressible as a pure fold over element internal-force kernels — a perfect
  fit for portable Clojure and for the actor pattern (1 run = 1 bounded simulation, the
  CFL step budget is the loop bound, no unbounded inner loop).
- **Nonlinearity is local**: large rotation, plastic flow and contact only change
  `F_int`/`F_contact`, never a matrix factorization. This keeps every module a pure
  function of state.
- The cost — **conditional stability** (`Δt < L_min/c`) — is acceptable for
  verification-scale crash cases and is mitigated by mass scaling.

## Module boundaries (the seams that stay fixed across sessions)

```
linalg     value-level vec3 / mat3 / sym-tensor (Voigt) — no mutable globals
mesh       node table, element connectivity, lumped-mass assembly
material   pure constitutive update:  (update mat σ^n Δε dt) → {:stress :state}
element    pure (internal-force el nodes-disp mat-state) → {:fint :dt-crit :state}
contact    pure penalty force from signed gaps
integrate  central-difference driver folding element fints; CFL Δt; energy ledger
keyword    *.k* deck → model data (data, not code)
```

The invariant: **`material`, `element`, `contact` are pure** — they take state and
return forces/new-state, never mutate. Only `integrate` owns the time loop, and it is a
reduction, so any host can checkpoint/replay it (audit-ledger friendly, like the other
actors' StateGraphs).

## Staged roadmap (本格, multi-session)

- **S0 — explicit core (this session).** linalg + mesh + lumped mass + truss & 1-pt hex
  element + linear-elastic & J2 material + central-difference integrator + CFL/mass
  scaling + energy balance. Demos: 1-D elastic wave (wave-speed check) and Taylor bar
  (plastic mushrooming). Verification tests green.
- **S1 — materials & contact.** Johnson-Cook (rate + thermal) — **landed**
  (`material/johnson-cook-flow-stress` + `stress-update-jc-3d`, a bisection return map
  on the nonlinear rate/thermal flow surface; reduces to linear J2 at n=1,C=0,isothermal).
  Adiabatic self-heating (`adiabatic-temperature-rise`, Taylor–Quinney) and JC ductile
  damage + erosion (`stress-triaxiality` / `johnson-cook-fracture-strain` /
  `accumulate-damage`) — **landed**. Penalty contact **Coulomb friction**
  (`contact/plane-traction` / `tangential-velocity` / `forces-with-friction`) — **landed**.
  Linear **kinematic hardening** (`material/axial-update-kinematic`, Prager back stress →
  Bauschinger effect for cyclic crush reversal; **dispatched from `axial-update`** so a
  truss can use `:kinematic` end-to-end) and the general **3-D combined
  isotropic+kinematic** J2 return (`stress-update-combined-3d`, deviatoric back-stress
  tensor; reduces to isotropic J2 at H_kin=0 and 3-D kinematic at H_iso=0) — **landed**,
  now **dispatched from `stress-update-3d`** so hex elements / the integrator can use
  `:combined` end-to-end (back stress threads through the hex mat-state). Still to come:
  deformable node-to-surface (master-segment) contact, and wiring damage/erosion into
  the element internal-force assembly.
- **S2 — structural elements.** Hourglass **energy metering** for the 1-pt hex
  (`hex-force` now returns `:hg-energy = ½ k_hg Σα q_α²`, verified ~0 under uniform
  strain and excited by a pure hourglass mode — the under-stabilization diagnostic) —
  **landed**. Penalty **tied/spotweld** constraints (`contact/tie-force` /
  `tie-forces`, a bilateral spring on two nodes' separation; spotweld = coincident
  rest) — **landed**. Still to come: Belytschko-Tsay shell, deformable surface ties.
- **S3 — implicit path.** Newmark + Newton-Raphson with a sparse linear solve (CG) for
  statics / springback, sharing the same `material`/`element` kernels.
- **S4 — deck coverage.** Broaden `*.k* keyword parsing (*CONTROL, *SECTION, *DEFINE,
  *BOUNDARY, *LOAD) and add a binary-state-plot-style result export.

## Consequences

- No native speed; verification-scale, not production-mesh-scale — acceptable, since the
  consumer is a *design-closure check*, not a certification run.
- Determinism + purity make every step checkpointable, matching the actor audit-ledger
  ethos used across com-junkawasaki.
