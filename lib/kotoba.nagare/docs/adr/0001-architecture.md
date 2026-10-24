# ADR-0001 — nagare-clj architecture: a pure-`.cljc` finite-volume CFD kernel

- Status: Accepted
- Date: 2026-06-27
- Context tags: solver, CFD, finite-volume, OpenFOAM-class, portable-cljc

## Decision

Build an OpenFOAM-class **unstructured finite-volume CFD** solver as a
zero-third-party-dependency `.cljc` library, so the *same* kernel runs on the JVM, SCI,
ClojureScript, GraalVM and kotoba-clj (WASM). The design actor injects it as a port to
*verify* aero/thermal behaviour; there is no PETSc, no MPI, no OpenFOAM runtime.

## Why collocated FVM, and why pure Clojure

- **Finite volume** is conservative by construction (face flux leaving a cell enters its
  neighbour exactly), which is what makes coarse verification meshes trustworthy.
- A **collocated** arrangement (U and p at cell centres) keeps the data model simple —
  one value per field per cell — at the cost of needing **Rhie–Chow** flux interpolation
  to suppress the checkerboard pressure mode. We pay that price to stay portable.
- Each discretization operator assembles a sparse **`fvMatrix`** from the mesh's
  `owner`/`neighbour` arrays; the matrix is plain data, and the **Krylov solvers (PCG,
  BiCGStab) are pure Clojure**. No native linear algebra ⇒ runs in a browser tab.
- 1 solve = 1 bounded simulation (outer-iteration / time-step budget is the loop bound),
  matching the actor pattern's "no unbounded inner loop" discipline.

## Module boundaries (the seams that stay fixed across sessions)

```
mesh       points / faces / owner / neighbour / cells / boundary patches;
           derived geometry: cell volumes, face areas+normals, centroids, deltas
field      volField + boundaryField (fixedValue, zeroGradient, noSlip, …) — data
fvm        operator → fvMatrix:  ddt / div / laplacian / grad; interpolation schemes;
           Rhie–Chow face flux. Pure functions of (mesh, field) → matrix.
linsolve   sparse matrix + Jacobi/GS smoothers + PCG (sym) + BiCGStab (asym)
solver     SIMPLE (steady) / PISO / PIMPLE (transient) coupling loops
turbulence k-ε, k-ω SST eddy-viscosity closures (added on top of momentum)
case       OpenFOAM case-dir subset reader (controlDict / polyMesh / 0)
```

The invariant: **`fvm` operators are pure** `(mesh, field, scheme) → fvMatrix`; the
solver loop only *assembles* matrices and *calls* `linsolve`. State (the fields after N
correctors) is a value, so any host can checkpoint/replay the run.

## Staged roadmap (本格, multi-session)

- **S0 — foundation + cavity (this session).** Unstructured mesh (built from a
  structured block so geometry is exact), volField/boundary, `fvm` grad/div/laplacian,
  PCG + BiCGStab, and a **PISO** loop solving the lid-driven cavity (icoFoam analogue).
  Verified against the Ghia et al. centreline. Tests green.
- **S1 — steady SIMPLE.** simpleFoam analogue with under-relaxation — **landed**
  (`solver/simple-step` + `advance-simple`: implicit momentum under-relaxation defining
  `rAU`, one corrector with the unrelaxed new pressure, explicit pressure
  under-relaxation; verified to converge to the same Ghia-band cavity centreline as
  transient PISO). Stability monitoring via `diagnostics/courant` + `cell-peclet`
  (the `u·Δt/Δx` and `u·Δx/ν` numbers), a `fvm/continuity-defect` (∇·U) check, and the
  OpenFOAM-style normalized `linsolve/scaled-residual` per-equation monitor — **landed**.
- **S2 — schemes & non-orthogonality.** Standalone **passive scalar transport**
  (`fvm/convection-diffusion`, steady upwind `div(φ,ψ) − laplacian(Γ,ψ)` — the thermal
  building block, verified to obey the discrete maximum principle) — **landed**. A
  second-order **linear-upwind** scheme by deferred correction (`transport/solve
  :linear-upwind` — verified to cut the L2 error vs the analytic exponential below
  first-order upwind) — **landed**, and **lifted into the momentum div** (opt-in
  `:div-scheme :linear-upwind` in the PISO `step`, lagged deferred correction — verified
  to deepen the lid-cavity centreline dip toward the Ghia value vs first-order upwind
  while still converging) — **landed**. A **limited (TVD)** variant
  (`transport/solve :limited` — clamps the reconstructed face value into the local
  cell-value range, restoring the maximum principle while keeping 2nd-order accuracy;
  verified bounded *and* more accurate than upwind) — **landed**. Still to come: explicit
  non-orthogonal correction, bounded laplacian.
- **S3 — turbulence.** k-ε then k-ω SST, wall functions; verify a flat-plate / channel.
- **S4 — case IO.** Parse a real OpenFOAM case directory (polyMesh + dictionaries) and a
  general unstructured (non-block) mesh; VTK-ish result export.

## Consequences

- No native speed; verification-scale meshes (10³–10⁵ cells), not production LES —
  acceptable, since the consumer is a *design-closure check*.
- Purity + value-state fields make each corrector checkpointable, matching the
  com-junkawasaki actor audit-ledger ethos.
