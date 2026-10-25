# nagare-clj (流れ)

[![CI](https://github.com/kotoba-lang/nagare/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/nagare/actions/workflows/ci.yml)

A clean-room **finite-volume CFD** kernel in portable Clojure — the OpenFOAM-class half
of the simulation stack. Every namespace is `.cljc`, designed for **Clojure-on-WASM
hosts** (SCI, ClojureScript, GraalVM, kotoba-clj) as well as the JVM, with **zero
third-party dependencies** — no PETSc, no native BLAS, no OpenFOAM runtime. An
unstructured collocated finite-volume solver: Gauss discretization of the
incompressible Navier–Stokes equations, pressure–velocity coupling by SIMPLE / PISO, and
Krylov linear solvers, all in pure Clojure over `double` arrays.

Sibling of [kudaki-clj](https://github.com/com-junkawasaki/kudaki-clj) (砕き — the
LS-DYNA-class explicit structural / crash kernel). Together they are the two physics
engines the [vehicle-design-actor](https://github.com/com-junkawasaki/vehicle-design-actor)
calls to *verify* a closed design: **nagare** for aero/thermal, **kudaki** for
crashworthiness.

> 流れ = flow. OpenFOAM's home turf is the external aerodynamics and internal
> thermofluids of a vehicle — drag, lift, cooling, cabin HVAC.

## Why pure `.cljc` (org placement)

Per the three-way rule, the **reusable** solver kernel lives in **com-junkawasaki**;
**public-benefit** instances live in **etzhayyim**; **business/private** deployments live
in **gftdcojp**. A native-dep-free FVM kernel runs the *same* code in a browser tab
(SCI/cljs), a GraalVM native image, and a kotoba-clj WASM pod — injected as a port by the
design actor, no FFI, no MPI cluster required for the verification-scale cases.

## The method (OpenFOAM, in one paragraph)

Integrate the conservation laws over each finite **control volume** (cell) and apply the
divergence theorem: volume integrals of `div`/`laplacian` become **sums of face fluxes**.
Each discretization operator (`fvm/ddt`, `fvm/div`, `fvm/laplacian`) assembles a sparse
**`fvMatrix`** — a diagonal plus owner/neighbour off-diagonals indexed by the mesh's
`owner`/`neighbour` face arrays. Velocity and pressure are **collocated** at cell
centres, so the SIMPLE/PISO loop adds a **Rhie–Chow** face-flux interpolation to kill the
checkerboard mode: solve a momentum predictor for `U*`, form a pressure-Poisson equation
from the discrete continuity defect, correct `U` and the face fluxes, repeat. The linear
systems are solved by **PCG** (symmetric pressure) and **BiCGStab** (asymmetric
momentum) with diagonal/ILU preconditioning.

## Modules (`nagare.*`)

Landed modules carry a ✓; planned ones are marked.

```
mesh        ✓ unstructured polyMesh: points, faces, owner/neighbour, cells, boundary
              patches; cell volumes, face areas/normals, centroids, discrete ∮dS=0
field       ✓ volScalarField / volVectorField + boundary conditions
              (fixedValue, zeroGradient, noSlip, fixedFluxPressure)
fvm         ✓ fvMatrix: ddt, div (upwind), laplacian, grad (Green–Gauss), Rhie–Chow;
              convection-diffusion assembler; continuity-defect (∇·U)
linsolve    ✓ Jacobi/Gauss-Seidel smoothers, PCG, BiCGStab, normalized residual
solver      ✓ PISO (transient) + SIMPLE (steady); opt-in linear-upwind momentum div
transport   ✓ scalar transport with upwind / linear-upwind / limited-TVD schemes
diagnostics ✓ Courant and cell-Péclet numbers
demo        ✓ lid-driven cavity (icoFoam analogue), Ghia-centreline verification
case        … OpenFOAM case-dir reader                                   (planned, S4)
turbulence  … RANS k-ε / k-ω SST eddy viscosity                          (planned, S3)
```

## Status / roadmap

Built **本格 (full-scale) across several sessions**; see `docs/adr/0001-architecture.md`
for the staged roadmap. **Landed so far (29 tests / 598 assertions, all green):**

- **S0** — unstructured mesh (discrete-Gauss verified), fields/BCs, fvm operators,
  Krylov solvers (PCG/BiCGStab, MMS Poisson 2nd-order convergence).
- **S1** — **PISO** transient + **SIMPLE** steady pressure–velocity coupling (both
  reproduce the Ghia cavity centreline; determinism/checkpointing verified), plus full
  convergence monitoring (continuity defect ∇·U, Courant/Péclet, normalized residual).
- **S2 (in progress)** — passive **scalar transport** with **upwind / linear-upwind /
  limited-TVD** convection (verified vs the analytic exponential & max-principle), and
  linear-upwind **lifted into the momentum div** (deepens the cavity dip toward Ghia).
- **Pending** — non-orthogonal correction (needs a skewed-mesh generator), turbulence
  (S3), OpenFOAM case-dir IO (S4).

```bash
kbb -M:run      # lid-driven cavity, prints centreline u-velocity profile
kbb -M:test     # verification suite (Poisson convergence, PCG, cavity centreline)
```
