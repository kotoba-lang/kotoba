# kudaki-clj (砕き)

[![CI](https://github.com/kotoba-lang/kudaki/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kudaki/actions/workflows/ci.yml)

A clean-room **explicit nonlinear structural dynamics** kernel in portable Clojure —
the LS-DYNA-class half of the simulation stack. Every namespace is `.cljc`, designed
for **Clojure-on-WASM hosts** (SCI, ClojureScript, GraalVM, kotoba-clj) as well as the
JVM, with **zero third-party dependencies** — no BLAS, no native solver. The crash /
impact / drop / forming solver: central-difference explicit integration of the
semi-discrete equations of motion, element-by-element internal force, rate-dependent
plasticity, and penalty contact.

Sibling of [nagare-clj](https://github.com/com-junkawasaki/nagare-clj) (流れ — the
OpenFOAM-class finite-volume CFD kernel). Together they are the two physics engines the
[vehicle-design-actor](https://github.com/com-junkawasaki/vehicle-design-actor) calls to
*verify* a closed design: **kudaki** for crashworthiness, **nagare** for aero/thermal.

> 砕き = crushing. LS-DYNA's home turf is the controlled crush of a body-in-white into
> a barrier — energy absorbed by the plastic folding of thin-walled structure.

## Why pure `.cljc` (org placement)

Per the three-way rule, the **reusable** solver kernel lives in **com-junkawasaki**;
**public-benefit** instances (e.g. open crash-safety studies) live in **etzhayyim**;
and **business/private** deployments live in **gftdcojp**. Keeping the kernel free of
native deps is what lets the *same* solver run in a browser tab (SCI/cljs), in a
GraalVM native image, and inside a kotoba-clj WASM pod — the design actor injects it as
a port, no FFI, no license server.

## The method (LS-DYNA, in one paragraph)

The semi-discrete equation of motion is `M a = F_ext − F_int(u)`. With a **lumped
(diagonal) mass matrix** the acceleration is trivially `a = M⁻¹ (F_ext − F_int)` — no
linear solve per step. State advances by **central difference**:
`v^{n+½} = v^{n−½} + Δt·a^n`, `u^{n+1} = u^n + Δt·v^{n+½}`. The internal force is
gathered **element by element** from the current deformation, so nonlinearity (large
rotation, plastic flow, contact) is just a different `F_int` — there is no global
stiffness matrix to refactor. The price is **conditional stability**: `Δt` must stay
under the CFL limit `Δt_crit = L_min / c` (`c = √(E/ρ)`, the dilatational wave speed),
which is why explicit codes take millions of tiny steps and why **mass scaling** exists.

## Modules (`kudaki.*`)

Landed modules carry a ✓; planned ones are marked.

```
linalg    ✓ vec3, 3×3 matrices, symmetric Voigt tensors (deviator, von-Mises, ddot)
mesh      ✓ nodes, element connectivity, lumped (diagonal) mass, element volumes
material  ✓ elastic; J2 radial return; Johnson-Cook (rate+thermal) + adiabatic
            self-heating; JC ductile damage + erosion; isotropic / kinematic
            (Bauschinger) / combined 3-D hardening
element   ✓ truss/rod + 1-pt hex solid with hourglass control & energy metering;
            internal-force kernels + per-element critical Δt
contact   ✓ penalty node-to-plane, Coulomb friction, tied/spotweld constraints
integrate ✓ explicit central-difference loop, CFL Δt, mass scaling, energy ledger,
            fixed-DOF constraints
demo      ✓ Taylor bar impact + 1-D elastic wave canonical verifications
keyword   … LS-DYNA *.k* deck parser                                     (planned, S4)
shell     … Belytschko-Tsay shell element                               (planned, S2)
```

## Status / roadmap

Built **本格 (full-scale) across several sessions**; see `docs/adr/0001-architecture.md`
for the staged roadmap. **Landed so far (45 tests / 185 assertions, all green):**

- **S0** — explicit central-difference kernel, truss + 1-pt hex (uniaxial/shear/rigid
  patch tests), elastic + J2; verified energy balance, wave speed √(E/ρ), Taylor bar.
- **S1** — **Johnson-Cook** (rate + thermal, bisection return) + **adiabatic heating**;
  **JC ductile damage + erosion**; **Coulomb friction** + **spotweld ties**; isotropic /
  kinematic (Bauschinger) / **combined 3-D** hardening.
- **S2 (in progress)** — 1-pt hex **hourglass energy metering** (the under-stabilization
  diagnostic).
- **Pending** — Belytschko-Tsay shell, master-segment deformable contact, implicit
  statics (S3), `.k` deck coverage (S4).

```bash
kbb -M:run      # Taylor bar + elastic wave demos
kbb -M:test     # verification suite (energy balance, wave speed, J2 return-map)
```
