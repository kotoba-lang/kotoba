# Vehicle Design Actor — a concept generator sealed behind physics

## 1. Premise: what a design proposer is, and what it is missing

A generative vehicle-design agent — an LLM or generative-CAD model —
is extraordinary at *spanning the concept space*: body style, packaging,
powertrain layout, a target curb mass that hits the marketing brief. What
it is **not** is a physics engine. Ask it for a 1500 km city car and it
will gladly hand you a 1100 kg concept, because nothing in its objective
forces the energy store to actually fit the mass and volume budget it
just wrote down.

So the design problem is **not** "use a model to design a car." It is
**"how do we confine the proposer inside a trust boundary"** so that bold
concepts can be explored but only *physically closed* designs leave the
actor as a spec. Everything below follows from that — and it is the exact
mirror of the [robotaxi actor](../../robotaxi-actor), where a research VLA
is confined behind a SafetyGovernor.

| robotaxi-actor | vehicle-design-actor |
|---|---|
| Alpamayo-R1 proposes a **trajectory** | DesignProposer proposes a **concept** |
| SafetyGovernor verifies against the **ODD + collision check** | PhysicsGovernor verifies against **conservation laws** |
| reject → **MRC** (safe stop) | infeasible → **rejected spec** (the design-side MRC) |
| teleop sign-off (`interrupt-before`) | engineer sign-off (`interrupt-before`) |
| one run = one ~100 ms **planning tick** | one run = one **design pass** |

## 2. Actor topology

```
VehicleDesignActor (one design = one supervised run)
│
├── DesignProposer ……… concept generator (LLM / gen-CAD). PROPOSAL ONLY.
│
├── PhysicsGovernor ……… INDEPENDENT censor — conservation laws
│     ├── mass closure …… solve the mass spiral to a fixed point
│     ├── energy balance … road load → store size (per powertrain)
│     ├── packaging ……… store volume ≤ envelope
│     └── gross / fraction  GVWR + store-mass-fraction gates
│
├── Powertrain models …… :bev (pack) | :fcev (tank + stack + buffer)
│     the ONLY part of the design that branches on powertrain
│
└── Design review ……… human engineer sign-off before release (interrupt)
```

Principles (deliberately the same three as robotaxi):

1. **The proposer is the lowest-trust node and never emits a spec
   directly.** Its concept is always censored by the PhysicsGovernor.
2. **Closure or fall-back.** A concept that does not close falls back to a
   *rejected spec* carrying the violated gates — the design analogue of an
   MRC. Nothing infeasible is ever released.
3. **Everything is checkpointed** (Datomic in prod, in-mem in dev), so
   "why is this car 1480 kg?" is a query over the audit ledger: proposal →
   mass-spiral history → verdict → emit.

## 3. The mass spiral — why this needs a solver, not a formula

A car's energy store is sized for its range, but a bigger store makes the
car heavier, which raises the energy it burns per km, which demands a
bigger store. For feasible designs this is a contraction and converges in
a handful of iterations:

```
curb₀ = proposer's optimistic guess
repeat:
  store   = size(powertrain, operating_mass = curb + occupants, range)
  curb'   = glider + store.mass + motor
until |curb' − curb| < 1 kg     →  CONVERGED (fixed point)
   or  curb' > 1.05 · GVWR       →  DIVERGED  (mass-spiral runaway → reject)
```

For over-reach (too much range for the cell/tank technology) the map is
**not** a contraction — curb climbs every iteration. That divergence is
the governor's reject signal: it is *physically meaningful*, not a tuning
artifact. The whole loop is bounded (≤60 iterations) and encapsulated in
one graph-node call, so one graph run is still one auditable design pass.

## 4. BEV vs FCEV — same mission energy, two stores

Road load (rolling + aero, cycle-blended) gives the **mechanical** energy
at the wheels per km — identical for both powertrains. The split is only
in how that energy is stored and the path efficiency back to it:

- **BEV.** `nominal_kWh = range · consumption / DoD`, where
  `consumption = wheel_energy / η(battery→wheel) + aux`. Pack mass =
  `nominal_kWh / 175 Wh·kg⁻¹`, volume = `nominal_kWh / 0.45 kWh·L⁻¹`.
  Tends to be **mass-limited** — the pack is the heaviest single item.

- **FCEV.** `H2_kg = range · consumption_LHV / LHV`, where the electric
  demand is up-converted through the fuel cell (`η ≈ 0.53`). Tank-system
  mass = `H2_kg / 0.055` (700-bar type-IV gravimetric), plus stack
  (`P / 2 kW·kg⁻¹`) and a small buffer battery. Tends to be
  **volume-limited** — compressed H₂ is ~0.04 kg/L and the tanks are bulky.

That is why, from one 500 km sedan brief, the actor returns a heavier-but-
compact BEV and a lighter-but-volume-tight FCEV — the trade is structural,
and the governor surfaces it as concrete margins (kg to GVWR, L to
envelope, store mass fraction).

## 5. Constants & extension points

All physics lives in `vdesign.powertrain/tech` (pack Wh/kg, FC efficiency,
H₂ gravimetric fraction, …) and `vdesign.proposer/classes` (glider mass,
Cd·A, package envelope per class). They reflect ~2026 production figures
and are the single place to retune. The DesignProposer is a deterministic
heuristic here; swapping it for a real generative-CAD or LLM node requires
no change to the governor or the graph — the trust boundary is the
`:propose → :govern` edge, and that is the whole point.

## 6. Real physics · real geometry · real motion plan (ADR-2607151600)

Everything above this section is deliberately **symbolic**:
`vdesign.simverify`'s crash check is a closed-form energy-balance
formula, `vdesign.cad`'s envelope is a coarse tessellated box, and
`vdesign.process`'s assembly order is a flat, data-only sequence — none
of it steps physics through time, machines real geometry beyond a
packaging box, or produces a Cartesian path a robot controller could
consume. `cloud-itonami`'s automotive pilot (ADR-2607151600) needed
more than that, so this repo grew three additional namespaces that
compose **only existing, already-real components elsewhere in
`kotoba-lang`** — no new physics engine, CAD kernel, or renderer was
written, and no new Rust (per this workspace's runtime-priority rule).

**`vdesign.simphysics`** is a genuine second physical model of the SAME
frontal-crash event `simverify` already checks, built directly on
[`kotoba-lang/physics-2d`](https://github.com/kotoba-lang/physics-2d) —
a real, tested, zero-dependency impulse-based 2D rigid-body solver,
restored 1:1 from the deleted `kami-physics-2d` Rust crate (not written
for this ADR). The design's own tessellated envelope becomes an AABB
`Collider2D`; a second, static (mass 0 = immovable) AABB stands in for
the crash-test barrier/fixture; `physics-2d/world-step` is called tick
by tick (real gravity/velocity integration, real brute-force AABB
collision detection, real impulse resolution + positional correction),
and the FULL per-tick trajectory is captured — `:sim-decel-g` (peak
tick-to-tick velocity change, converted to g) and
`:sim-crush-distance-m` (peak observed AABB penetration) are both
**read off that real trajectory**, not invented after the fact.

This is honestly a 2D projection — `physics-2d` has no 3D solver — and
the barrier is immovable, which surfaces a genuinely useful (if
initially counter-intuitive) finding: **colliding with an immovable
anchor, the impulse's velocity change does not depend on the moving
body's own mass** — algebraically true of BOTH `physics-2d`'s
`resolve-contact` AND `crash.solver`'s own closed-form `a-g = (F/m)/g`
where `F ∝ m` (the mass term cancels in each). So `:sim-decel-g` is
mass-invariant in this model, by real physics, not a limitation unique
to the toy engine — impact SPEED is the lever that actually moves it,
and that is what `simphysics_test.cljc`'s sanity check exercises,
alongside an explicit assertion that mass alone does NOT move it
(documenting the finding rather than asserting a false relationship).

`simphysics/crosscheck` compares `:sim-decel-g` against `simverify`'s
existing `crash.solver` closed-form deceleration. Because
`physics-2d`'s impulse resolver has no crush-stiffness/force-deflection
model — any tick that first detects overlap fully zeroes the closing
velocity in ONE tick — its timestep `dt` is deliberately derived from
the design's own crush-length/impact-speed (the nominal transit time
across the crush zone) rather than picked arbitrarily. That choice
means a "boxcar" (instantaneous, constant) stop is, by exact kinematic
identity, always **2x** the closed form's own averaged/ramp
deceleration for the same speed and crush length — so the crosscheck's
tolerance band is centered on ~2x, not ~1x, and is documented in the
namespace as a coarse sanity check between two related idealizations,
explicitly **not** a validation of either model's absolute accuracy.

**`vdesign.scene`** bridges `vdesign.cad`'s tessellated envelope
(vertices + triangle indices) and `vdesign.simphysics`'s per-tick
trajectory into the exact vertex/normal/index + per-frame-transform
shape [`kotoba-lang/webgpu`](https://github.com/kotoba-lang/webgpu)'s
real, working `kami.webgpu.mesh` executor (`upload-mesh!`/
`render-frame!`, proven in `network-isekai`/`kami-app-amenominaka`)
already consumes. Two real, disclosed gaps had to be closed, not
hidden: (1) `vdesign.cad` produces no `:normals` — `face-normals`
computes real per-triangle flat normals via cross product; (2)
`vdesign.cad`'s tessellated positions are millimeters while
`vdesign.simphysics`'s trajectory is meters — `scene.cljc` converts
units. (An earlier draft of this bridge also assumed the mesh needed
re-centering around its geometric origin; `scene_test.cljc` caught that
this assumption was wrong — `vdesign.cad`'s sketch/extrude convention
already centers the XY footprint — and the fix is documented in the
namespace itself as a real, corrected finding, not silently dropped.)
The one honest limitation that remains: `kami.webgpu.mesh` is a
`.cljs`-only browser WebGPU executor, and this actor-only repo has no
browser to render into — `scene-for`'s output is verified for real
shape-correctness against that function's documented input contract,
not actually rendered to a canvas.

**`vdesign.motionplan`** extends `vdesign.process`'s existing real BOM +
4D assembly-order sequence (the giemon-factory `construction.order.json
:seq` pattern) into an ordered list of Cartesian waypoints, one per
assembly station, laid out along a straight line at a fixed pitch with
a working height derived from the design's own real envelope dims. This
is explicitly **not** an inverse-kinematics solver, a trajectory
optimizer, or a real robot-controller driver — a plausible, honestly
simplified station layout, walking the SAME station order
`vdesign.process/plan` already produces.
