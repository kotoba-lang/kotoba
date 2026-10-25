# kotoba-lang/physics

**SSoT for `kami.physics`** — collision layers + matrix as pure EDN (`.cljc`).

`kotoba.physics` is a thin facade. See ADR-2607102200 addendum 7.

`kotoba.physics.particles` is a VFX particle system: emitters, forces, ageing,
plane collision, deterministic from a seed. Emission is a RATE — the fractional
remainder is carried, so the count over a duration is the same at 30, 60 or 240
steps per second — and the integrator is held to its own closed form,
`x_n = x_0 + n dt v_0 + g dt^2 n(n+1)/2`, exactly. The generator is an explicit
int32 xorshift so the same seed gives the same particles on the JVM and in a
browser; golden values in the `.cljc` suite check that from both sides.

`kotoba.physics.cloth` is a solver: cloth and hair as position-based dynamics
(XPBD), with distance constraints, pins, sphere and plane colliders. Cloth and
hair are the same solver — a strand is a chain.

What it is held to, all of which is exact rather than visual: the constraint
residual falls monotonically with iterations; a free cloth never moves its own
centre of mass (constraints move their two particles by mass-weighted opposite
amounts); the solver is frame-indifferent under translation and rotation; a
pendulum swings at 2 pi sqrt(L/g) to within 0.2%; and compliance is a material
property, so sag is unchanged to 1e-9 between 20 and 80 iterations.

## Test

```sh
kbb -M:test
```
# Unified physics contract

`kotoba.physics.contract` is the zero-dependency CLJC boundary shared by
Kami Engine, Network Isekai, realtime rigid-body backends and engineering CAE
backends. Immutable EDN scenes use SI units and distinguish `step` from
finite-case `solve`. Fidelity is one of `:realtime`, `:reduced-order` or
`:high-fidelity`; capability checks require an exact fidelity match.

Results carry explicit, scope-specific qualification. A completed solve never
implies experimental validation or design-signoff. Collision layers below
remain scene configuration, rather than a competing simulation engine.
