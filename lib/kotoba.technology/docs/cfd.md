# CFD Technology

`kotoba.technology/:cfd` is the stable business-facing handle for computational
fluid dynamics.

Current implementation references:

- `kotoba-lang/aero`
- `kotoba-lang/cae-solver`

The business contract is an EDN simulation case plus a solver-kind and an
auditable result payload. High-fidelity backends can replace reduced-order
solvers without changing business workflows.
