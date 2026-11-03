# vehicle-design-actor

A **clean-sheet vehicle design** actor — given requirements (class, range,
payload, top speed) it designs a car *from zero* and sizes its energy
system for **either a battery-electric (BEV) or a hydrogen fuel-cell
(FCEV)** powertrain. Built on this workspace's
[`langgraph-clj`](https://github.com/kotoba-lang/langgraph)
StateGraph runtime (portable `.cljc`, supervised superstep loop,
interrupts, Datomic/in-mem checkpoints) — the same runtime the
`robotaxi-actor` rides on.

> **Why an actor layer at all?** A generative design proposer (LLM /
> CAD agent) is a brilliant *concept generator* but it does **not respect
> conservation laws** — it will happily target a 1500 km city car at
> 1100 kg. This project seals the proposer into a single node and wraps
> it with an independent **PhysicsGovernor** that closes the mass spiral,
> balances energy, and checks packaging — and **rejects** any concept
> that does not close.

It is the design-side mirror of the robotaxi actor: there, a research
VLA is sealed behind a SafetyGovernor that can reject any *trajectory*;
here, a concept generator is sealed behind a PhysicsGovernor that can
reject any *design*.

## The core contract

```
requirements + powertrain (:bev | :fcev)
        │
        ▼
   ┌──────────────┐  concept (untrusted)  ┌──────────────────┐
   │ DesignProposer│ ────────────────────▶ │ PhysicsGovernor  │ (independent)
   │  (sealed)     │  target mass · power  │ mass closure ·   │
   └──────────────┘                        │ energy · package │
                                           └────────┬─────────┘
                                      closes ◀──────┴──────▶ infeasible → rejected
                                        │
                                 engineer sign-off  [interrupt]
                                        │
              (a) ┌───────────────────────────────────┐
                  │ SimGovernor — genesis/cae-compat   │ structural · clash · axle
                  │ + kami-shugyo-style per-env DR      │ survives? ◀──▶ rejected
                  └──────────────┬────────────────────┘
                                 │ survives
              (b) ┌───────────────────────────────────┐
                  │ ProcessPlanner — BOM → CAM (G-code) │ → kotoba Datom log
                  │ → 4D assembly order (giemon :seq)   │   (verification + mfg facts)
                  └──────────────┬────────────────────┘
                                 ▼  released spec + process, all datafied
```

**The proposer never ships a design the PhysicsGovernor hasn't closed.**
That single invariant is what lets a bold concept generator produce a
manufacturable spec — and the **mass spiral** (heavier car → bigger store
→ heavier car …) is solved as a bounded fixed-point inside one graph run.

## Run

```bash
kbb -M:dev:run     # clean-sheet a sedan as BEV and FCEV, then reject an over-reach
kbb -M:dev:test    # the closure contract as executable tests
```

Demo output clean-sheets the **same** 500 km sedan as a BEV (~67 kWh,
~1480 kg) and as an FCEV (~3 kg H₂, ~1230 kg — lighter, but tank-volume
limited), then pushes a **1500 km city BEV** whose mass spiral runs away
→ the PhysicsGovernor rejects it (the design-side Minimal Risk Condition).

## BEV vs FCEV — where the design splits

Everything upstream of the energy store is **propulsion-agnostic** (one
glider, one road-load model). Only `vdesign.powertrain` branches:

| | BEV | FCEV |
|---|---|---|
| Store | Li-ion pack (175 Wh/kg, 0.45 kWh/L pack-level) | 700-bar H₂ tank (5.5 wt% system) + FC stack + buffer |
| Path η (source→wheel) | ~0.84 (battery→wheel · regen) | ~0.40 (H₂ LHV → stack 0.53 → wheel) |
| Sized from | nominal kWh = range · consumption / DoD | H₂ kg = range · consumption / LHV |
| Tends to be limited by | **mass** (pack is heavy) | **volume** (H₂ tanks are bulky) |

Both feed the **same** mass-closure spiral, so the two architectures fall
out of identical requirements as physically distinct vehicles.

## Layout

| File | Actor / role |
|---|---|
| `src/vdesign/proposer.cljk` | **DesignProposer** — the contained concept generator (heuristic mock) |
| `src/vdesign/physics.cljk` | **PhysicsGovernor** — mass closure · energy balance · packaging gates |
| `src/vdesign/powertrain.cljk` | BEV / FCEV energy-system models (the only powertrain branch) |
| `src/vdesign/simverify.cljk` | **(a) SimGovernor** — structural · clash · axle on the Isaac/genesis-compat surface + per-env DR |
| `src/vdesign/process.cljk` | **(b) ProcessPlanner** — BOM → CAM (G-code) → 4D assembly order |
| `src/vdesign/datom.cljk` | kotoba Datom-log (EAVT) representation — verification + mfg as facts |
| `src/vdesign/design.cljk` | **VehicleDesignActor** — the `langgraph` StateGraph (1 run = 1 design pass) |
| `src/vdesign/sim.cljk` | demo driver |
| `src/vdesign/simphysics.cljk` | **real time-stepped physics** — `physics-2d`-backed frontal-crash rigid-body simulation |
| `src/vdesign/scene.cljk` | bridges tessellated geometry + the physics trajectory into `kami.webgpu.mesh`'s real input shape |
| `src/vdesign/motionplan.cljk` | extends the 4D assembly order into Cartesian assembly-station waypoints |
| `test/vdesign/closure_contract_test.cljk` | the closure + verify + process invariants, executable |

## (a) Simulate, (b) datafy the build — the kami-engine bridge

A closed spec is not a finished design. Two downstream stages connect it to
the workspace's simulation and manufacturing fabric:

- **(a) `simverify` → Isaac / Cosmos sim.** The released spec is verified
  for crash-load paths, package clash and axle loading against the
  [**com-nvidia-isaac-sim**](https://github.com/kotoba-lang/com-nvidia-isaac-sim)
  (`isaacsim.core.api`, formerly kami-genesis) /
  [**fea**](https://github.com/kotoba-lang/fea) (formerly kami-cae) surface, then
  hardened with **[com-nvidia-isaac-lab](https://github.com/kotoba-lang/com-nvidia-isaac-lab)-style
  (formerly kami-shugyo) per-env domain randomization** (mass
  ±8 %, structure ±6 %, crash pulse ±10 %) for a sim-to-real margin — the
  same clean-room Isaac-compat stack kami-engine matured in ADR-0034. A
  structural failure downgrades even a physics-closed design to *rejected*
  (a second governor). The DR batch is seeded, so verdicts reproduce.

- **(b) `process` → datafied assembly.** The verified spec explodes into a
  **BOM**, a **CAM** process (toolpaths → **G-code**, in kami-cam's
  vocabulary), and a **4D assembly order** (the giemon-factory
  `construction.order.json :seq` pattern) — where the BEV and FCEV lines
  diverge exactly at their energy systems (`battery-pack-install` /
  `charge-to-soc` vs `h2-tank-install` / `h2-leak-test` / `h2-fill`).

Both stages write **kotoba datoms** (EAVT, Datomic-isomorphic — the same
log the `nvidia_cosmos-compat` / `nvidia_isaac-compat` actors speak), so
"why is station 4 the bottleneck?" or "which parts share tool T-03?" is a
Datalog query, not a spreadsheet. **Yes — the assembly process is datafied,
down to the G-code and the takt time.**

## Real physics · real geometry · real motion plan (ADR-2607151600)

`vdesign.simverify`/`vdesign.cad`/`vdesign.process` above are all
**symbolic-only**: a closed-form safety factor, a coarse tessellated
box, and a data-only assembly sequence — zero physics timestep, zero
rendering, no Cartesian robot path. ADR-2607151600 (the automotive pilot
for `cloud-itonami`'s real-engineering-simulation integration) adds
three namespaces that turn those symbolic outputs into a genuinely
time-stepped, geometrically real, renderable simulation — **composing
only existing, already-real components in the `kotoba-lang` workspace**,
no new physics engine, CAD kernel, or renderer, and no new Rust:

- **`vdesign.simphysics`** — models the frontal-crash dispatch event as
  an actual `physics-2d` (a real, tested, zero-dep impulse-based 2D
  rigid-body solver, restored 1:1 from the deleted `kami-physics-2d`
  Rust crate) simulation: the vehicle's real tessellated packaging
  envelope becomes an AABB collider, moving at the real 56 km/h
  frontal-crash-test speed toward a static barrier, stepped tick by
  tick through `physics-2d/world-step`. `:sim-decel-g` and
  `:sim-crush-distance-m` are derived from the ACTUAL simulated
  velocity/position trajectory, not invented. `crosscheck` compares
  this against `vdesign.simverify`'s existing closed-form
  `crash.solver` model — **honestly documented as a coarse, ~2x-centered
  sanity crosscheck between two related idealizations (a discrete
  "boxcar" stop vs. a uniform-deceleration closed form), never a
  validation of either model's absolute accuracy.** A genuinely
  surprising, verified finding from building this: vehicle MASS alone
  does not change `:sim-decel-g` in either model — colliding with an
  immovable barrier, the impulse's velocity change is mass-independent
  (real physics, not a bug) — so the directional sanity check that
  actually holds is impact SPEED, not mass; see the namespace docstring
  and `simphysics_test.cljc` for the full derivation.
- **`vdesign.scene`** — bridges `vdesign.cad`'s real tessellated
  envelope mesh + `vdesign.simphysics`'s per-tick trajectory into the
  exact vertex/normal/index + per-frame-transform shape
  `kotoba-lang/webgpu`'s real, working `kami.webgpu.mesh` executor
  (`upload-mesh!`/`render-frame!`) already consumes. Two real,
  disclosed gaps are bridged (`vdesign.cad` has no `:normals`, and its
  positions are millimeters vs. `physics-2d`'s meters) — see the
  namespace docstring for both, including a wrong first assumption
  (that the mesh needed re-centering) this repo's own tests caught and
  corrected. **Honest limit:** `kami.webgpu.mesh` is a `.cljs`-only
  browser WebGPU executor; this actor-only repo has no browser to
  actually render into, so `scene-for`'s output is verified for
  shape-correctness (`scene_test.cljc`), not rendered.
- **`vdesign.motionplan`** — extends `vdesign.process`'s existing real
  BOM + 4D assembly-order sequence into an actual ordered list of
  Cartesian waypoints, one per assembly station. **Not** an
  inverse-kinematics solver or a robot-controller driver — a plausible,
  honestly-simplified straight-line station layout.

Run `kbb -M:test` (or `:dev:test` inside the monorepo checkout) —
these three namespaces' tests are part of the same suite.

## Status

Working reference model. The proposer is a deterministic heuristic and the
physics constants in `vdesign.powertrain/tech` reflect ~2026 production
technology — retune there as cells/tanks improve, or swap the proposer for
a real generative-CAD / LLM node behind the same StateGraph boundary.
See [`docs/DESIGN.md`](docs/DESIGN.md) and
[`docs/adr/0001-architecture.md`](docs/adr/0001-architecture.md).
