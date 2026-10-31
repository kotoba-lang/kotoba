# kami-engine-vphysics

[![CI](https://github.com/kotoba-lang/kami-engine-vphysics/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kami-engine-vphysics/actions/workflows/ci.yml)

Shared vehicle-physics primitives — road load, SI constants, aero force, range/energy sensitivity. **Purpose: domain physics math.** Used by vehicle-design-actor (energy sizing) and aero-clj (range loop).

Part of the clean-sheet vehicle-design / CAE stack (purpose-split shared libs).
Zero-dep portable `.cljc`. Run `kbb -M:test`.
## Unified Kotoba backend

`vphysics.backend/backend` exposes the SI road-load equations through
`kotoba.physics.contract` at `:reduced-order` fidelity. It consumes the same
scene/case envelope as game physics and CAE, but explicitly reports model
validation and design sign-off as not qualified until correlated evidence is
provided.
