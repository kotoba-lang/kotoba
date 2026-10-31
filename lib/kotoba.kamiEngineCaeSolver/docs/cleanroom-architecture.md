# Kotoba CAE clean-room architecture

## Scope

Kotoba implementations are written from published mathematical specifications,
public standards, and independently authored conformance tests. No source code,
non-public implementation detail, generated binary, or proprietary test vector
is copied from OpenFOAM, CalculiX, MPI, deal.II, MOOSE, or commercial products.
External projects are used only as interoperability targets and as separately
licensed reference executables where their license permits that use.

## Layers

1. `cae.solver` — stable dispatch contract.
2. `cae.high-fidelity` — portable numerical reference kernels.
3. `cae.protocol` — MPI-like rank, message, collective, halo and job schemas.
4. `cae.mesh` — neutral TRI/TET/VTK/Gmsh/OpenFOAM mesh interchange.
5. `cae.adapter` — host-process boundary; no solver source is linked into CLJS.
6. `cae.verification` — analytic, benchmark and experimental-data gates.
7. host implementations — independently written native/WASM Kotoba workers.

The host boundary allows Open MPI/MPICH, OpenFOAM, CalculiX, deal.II, MOOSE or
preCICE to be replaced incrementally by Kotoba implementations without changing
case descriptions or validation reports.

## Clean-room evidence

Each replacement backend must provide:

- a public specification and license record;
- independently authored reference equations and invariants;
- golden tests generated from analytic solutions or permitted datasets;
- a reproducible build hash and dependency/license bill of materials;
- explicit status `:reference`, `:external-unverified`, or `:validated`.

This is an engineering architecture, not legal advice; license review is still
required before distributing adapters or datasets.
