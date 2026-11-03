# kami-flow

KAMI Flow — orchestration layer for end-to-end digital implementation.

Restored from the legacy `kami-engine/kami-flow` Rust crate's `src/lib.rs`
(kotoba-lang/kami-engine, deleted in PR #82 "Remove Rust workspace from
kami-engine") as a zero-dependency, portable `.cljc` per ADR-2607010930
(`com-junkawasaki/root`, `90-docs/adr/`).

P10 integrated pipeline:

```
RTL -> PnR -> GDSII -> Verify/Power/DFT/SI/Yield -> STA -> DRC/LVS -> Signoff
```

## Scoping correction

This crate was earlier mistakenly recorded as out of scope / an unrelated
Node.js + Cypher graph-ingest tool. That description genuinely applies to
the sibling `graph/` subdirectory that shares the same `kami-flow/` folder
in `kami-engine` (a `neo4j_bulk_ingest.cypher`-based tool, unrelated to
digital-implementation orchestration) — it does **not** apply to this
crate's own `src/lib.rs`, which had never actually been inspected before
this restoration. Only `src/lib.rs` was ported here; `graph/` remains
correctly out of scope and untouched.

## What it does

`flow/run-minimal-flow` runs a trivial single-module design through the
full pipeline and produces a `SignoffReport`: parse -> place & route ->
export GDSII -> equivalence check -> power/IR-drop estimate -> DFT scan
insertion + ATPG -> signal-integrity (transmission line + eye diagram) ->
Monte Carlo yield + PVT corners -> STA -> DRC/LVS -> pass/fail signoff
checks against configurable `FlowThresholds`. `flow/render-signoff-html`
renders the report as a standalone HTML summary page.

It is a pure-data orchestrator — no GPU, no native FFI, no wasm-bindgen —
that calls into 7 already-restored sibling EDA crates, one dependency per
pipeline stage:

| Stage      | Dependency (pinned SHA)                                                                   | Namespace(s) used |
|------------|--------------------------------------------------------------------------------------------|--------------------|
| RTL        | [`kotoba-lang/rtl`](https://github.com/kotoba-lang/rtl) @ `4c2d6d5340a47cd310028482c6195c59d100de4d` | `rtl.hdl` |
| PnR/GDSII  | [`kotoba-lang/pnr`](https://github.com/kotoba-lang/pnr) @ `294a5e26ac54cea653540632f5aa7c2f72ee32c6` | `pnr.floorplan`, `pnr.gdsii` |
| Verify     | [`kotoba-lang/model-checking`](https://github.com/kotoba-lang/model-checking) @ `7595e47d44caec9600f260261cc8cab4c1a30a7e` (renamed from `kami-verify`) | `model-checking.equivalence` |
| Power      | [`kotoba-lang/power`](https://github.com/kotoba-lang/power) @ `3038529b859a34f4299a6301b3bf8d0cac49c0fe` | `power.estimation`, `power.ir-drop` |
| DFT        | [`kotoba-lang/dft`](https://github.com/kotoba-lang/dft) @ `e0d19766839963114838526e54f11b0503ad0166` | `dft.scan`, `dft.atpg` |
| SI         | [`kotoba-lang/signal-integrity`](https://github.com/kotoba-lang/signal-integrity) @ `66e8bacabcd4771e2b833dbea707711e110ec3d0` (renamed from `kami-si`) | `signal-integrity.transmission-line`, `signal-integrity.eye-diagram` |
| Yield      | [`kotoba-lang/yield`](https://github.com/kotoba-lang/yield) @ `31ee270a574da18bb602d58f8422f1350cdd11f4` | `yield.monte-carlo`, `yield.corner` |

STA and DRC/LVS are computed locally (as in the original Rust — there was
never a dedicated `kami-sta`/`kami-drc` crate).

## Compressible choked-flow contract (`flow.choked`)

`src/flow/choked.cljk` removes the demonstrated block recorded by the
open `flow.pressure` contract: its incompressible `restriction-mass-flow`
is explicitly valid only for small pressure ratios and under-predicts
choked flow. Cartridge / reactor / PEMFC hydrogen leak paths routinely
sit at large pressure ratios, so this namespace supplies the compressible
model:

- `critical-pressure-ratio` — pr* = (2/(k+1))^(k/(k-1)) from a
  caller-supplied gamma.
- `choked?` — explicit regime determination for a pressure ratio.
- `restriction-mass-flow` — 1-D isentropic ideal-gas orifice flow with
  the regime in the result (`:choked` / `:subcritical`). The two branches
  are continuous at pr = pr* (verified to machine epsilon in the tests).

Units are SI and carried in the result keys. Gas identity (specific gas
constant, gamma), pressures, temperature, area, and Cd are all explicit
caller inputs — nothing is defaulted, and real-gas effects are not
silently corrected.

## Notes on the port

- `pnr.gdsii/export-gdsii` is JVM-only (`java.io.ByteArrayOutputStream`),
  so `flow/run-minimal-flow` (which calls it to produce the GDSII
  artifact) is JVM-only too — the same constraint the original Rust crate
  had transitively via `kami_pnr::gdsii`.
- The original Rust used `serde_json` to hash/serialize `FlowInput` and to
  produce `run_minimal_flow_json`'s output. To keep the crate
  zero-dependency, this port substitutes `pr-str` (EDN) for JSON
  serialization — semantically equivalent (deterministic serialization of
  the same input/report data) but not byte-identical to the Rust JSON
  output.
- `Result<T, FlowError>` is ported as the `[:ok v]` / `[:error msg]`
  2-tuple convention already used elsewhere in this migration (e.g.
  `rtl.hdl/parse-verilog`).
- All names are kebab-cased (`run_minimal_flow` -> `run-minimal-flow`,
  `max_ir_drop_mv` -> `:max-ir-drop-mv`, etc).

## Size / tests

- `src/flow.cljk`: 392 lines.
- `test/flow_test.cljk`: 5 tests / 23 assertions (all 4 original Rust
  `#[test]`s ported 1:1, plus a namespace-loads smoke test) — 0 failures,
  0 errors.

```
kbb -M:test
```
## Fluid-pressure contract (`flow.pressure`)
`src/flow/pressure.cljc` is an executable contract for the
`:fluid-pressure-and-leak-cae` design domain of the magnesium-hydrogen-PEMFC
electric-drive system (see `com-junkawasaki/root`
`scripts/hermes-magnesium-systems-bots/system-scope.edn`):
- `darcy-weisbach-delta-p` — incompressible segment pressure drop (Pa);
  friction factor, density, velocity are all explicit caller inputs.
- `colebrook-friction-factor` — fixed-point solve of the Colebrook–White
  equation; the returned `:colebrook-residual` is the convergence evidence.
- `reynolds-number` — Re from density/velocity/diameter/viscosity.
- `restriction-mass-flow` — incompressible Bernoulli leak/restriction flow
  (kg/s); valid only for small pressure ratios (not choked flow).
- `series-pressure-drop` — composes labeled segments into a per-segment
  breakdown plus a total circuit drop.
Units are SI and carried in the result keys. No fluid properties, friction
factors, or hydrogen performance constants are baked in — unknown
measurements stay with the caller, who attaches provenance per component.
