# kami-engine-aero

[![CI](https://github.com/kotoba-lang/kami-engine-aero/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kami-engine-aero/actions/workflows/ci.yml)

Reduced-order **aerodynamic drag (Cd) solver** for clean-sheet vehicles, in
portable Clojure (`.cljc`). It replaces the *fixed Cd prior* the
[`vehicle-design-actor`](../vehicle-design-actor) assumes with a **computed,
decomposed Cd**, and feeds it back into the range / battery-size loop. The
case setup is **EDN**, the result is **kotoba datoms** — so a vehicle's
aerodynamics is queryable data, not a number in a slide.

This is the first of the automotive-CAE physics brought into the workspace as
clean-room kami-* / *-clj layers (the others: crash FEA, motor EM/thermal, FC
electrochemistry). The heavy high-fidelity backend (`kami-cfd`,
lattice-Boltzmann) plugs in later behind the **same case/datom interface**.

## Method — component build-up (the honest concept-stage Cd)

Pure potential-flow / panel methods give **zero drag** (d'Alembert's paradox),
so Cd cannot come from a panel solve. Instead drag is built up from viscous /
separation **components**, each scaled by a body shape descriptor in `[0,1]`:

```
Cd = forebody + afterbody + wheels + underbody + cooling + friction + induced
       │           │ (dominant)        │                    │
   nose round   boat-tail/fastback   flat floor        turbulent Cf × S_wet/A
```

Every count is traceable to a descriptor, so the output is a **decomposition**,
not a black box. All coefficients live in `aero.model/default` (edn-tunable),
exactly like `vehicle-design-actor`'s `powertrain/tech`.

## Run

```bash
kbb -M:run     # Cd for the same sedan as BEV vs FCEV + the range loop
kbb -M:test    # the aero contract (band, monotonicity, BEV<FCEV, datoms)
kbb -M:lint
```

Demo result (sedan, 120 km/h cruise, prior Cd 0.24):

| | Cd | CdA (m²) | vs prior 0.24 | dominant |
|---|---|---|---|---|
| **BEV**  | **0.248** | 0.57 | −1.3 % range | afterbody (886 cts) |
| **FCEV** | **0.267** | 0.61 | −4.3 % range | afterbody + cooling/underbody |

The BEV/FCEV split is **real and mechanistic**: an FCEV's rougher underbody
(tanks/exhaust) and larger cooling-open area add ~19 drag counts over a BEV's
flat battery floor → higher Cd → shorter range. The computed BEV Cd (0.248)
also **validates** the design actor's 0.24 prior to within 3 %.

## The design-loop closure (`aero.bridge`)

Aero force at cruise is `F = ½ρ·Cd·A·v²`; over a fixed range the aero energy
scales linearly with Cd. So a computed-vs-prior Cd delta maps directly to a
**range (or kWh) delta** — the same road-load aero term
`vehicle-design-actor/powertrain` uses, kept here so aero-clj demonstrates the
loop without a hard cross-repo dependency. Result is datafied:
`[case :aero.AeroCase/Cd 2479] [case :aero.AeroComponent/cdCount …]`.

## Layout

| File | Role |
|---|---|
| `src/aero/model.cljk` | edn-tunable build-up coefficients (the single table) |
| `src/aero/solver.cljk` | the `:rom-buildup` Cd solver (a `kami-cfd` LBM backend would share this contract) |
| `src/aero/case.cljk` | EDN case + class/powertrain → shape-descriptor priors |
| `src/aero/bridge.cljk` | Cd → road-load → range effect, datafied |
| `src/aero/native.cljk` | native backend descriptors (`kami-cfd` as adapter data, not authority) |
| `src/aero/lbm.cljk` | `:lbm` backend — shells out to the `kami-cfd` (Rust LBM) binary, calibrated to the rom-buildup reference |
| `src/aero/datom.cljc` | kotoba Datom-log (EAVT) emission |
| `src/aero/cli.cljc` | demo |
| `test/aero/aero_test.cljk` | the aero contract (band, monotonicity, BEV<FCEV, datoms) |
| `test/aero/model_test.cljk` | `aero.model`'s coefficient-table invariants |
| `test/aero/lbm_test.cljk` | `aero.lbm`'s shape mapping, calibration constants, and contract registration (no external binary invoked) |
| `test/aero/native_test.cljk` | native backend/result contract |

## Status

Working reduced-order reference. The `:rom-buildup` solver is engineering-useful
at concept stage; a validated `kami-cfd` (lattice-Boltzmann) backend implementing
the same `solve` contract is the next fidelity step (registered on the shared
contract via `aero.lbm`, calibrated but not yet the default). Constants in
`aero.model/default` are the single place to re-fit against CFD/wind-tunnel data.
See `docs/adr/0001-architecture.md`.
