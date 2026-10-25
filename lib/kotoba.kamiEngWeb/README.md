# kotoba-lang/kami-eng-web

Zero-dep portable `.cljc` — restored (scoped) from the legacy
`kami-engine/kami-eng-web` Rust crate (912-line `lib.rs` + `Cargo.toml` +
`test-visual.html`, deleted in kotoba-lang/kami-engine PR #82 "Remove Rust
workspace from kami-engine") as part of the **clj-wgsl migration**
(ADR-2607010930, `com-junkawasaki/root`).

This is the 4th member of the KAMI Engineering SDK family restored in this
migration, after `kami-eng-core` / `kami-eng-io` / `kami-eng-render`
(restored earlier as `kotoba-lang/{engineer,engineer-io,engineer-render}`
per the migration's `eng` -> `engineer` renaming decision; `kami-eng-web`
keeps its original name, since it is the first — and last — member of this
family to be restored under the `kami-` prefix per the assignment).

## What this is

The original crate was a `wasm-bindgen` entry-point layer: ~40 thin
`#[wasm_bindgen] pub fn` exports, each parsing/marshaling simple params or
JSON into a call on one of 17 sibling `kami-*` crates (`kami-eda`,
`kami-cad`, `kami-cam`, `kami-rtl`, `kami-cae`, `kami-spice`, `kami-pdk`,
`kami-pnr`, `kami-dft`, `kami-verify`, `kami-power`, `kami-si`, `kami-pkg`,
`kami-yield`, `kami-ip`, `kami-flow`, plus `kami-eng-core`/`kami-eng-io`/
`kami-eng-render`) and serializing the result to JSON for JS/TS
consumption. `test-visual.html` is a plain demo page: it loads the
compiled wasm module and draws canvas visualizations of each function's
output — no additional portable logic of its own.

None of `kami-eng-web`'s ~40 exports contain a *complete* portable
computation: every one delegates its actual work to one of those 16
*other*, still-unrestored `kami-*` crates. There is no `kami-eng-web`-owned
algorithm to restore as a whole program.

Rather than restore nothing, this crate extracts the small amount of
genuinely portable **input-shaping logic** that lived directly in `lib.rs`
itself, ahead of each external-crate call: string -> enum/keyword parsing
and fixed default-value struct literals.

| Namespace | From (fn in original `lib.rs`) | Purpose |
|---|---|---|
| `eng-web.tech-node` | `parse_tech_node` | Tech-node name string -> keyword (N180..N2) |
| `eng-web.package` | `pkg_estimate`/`pkg_thermal` | Package-type presets (QFP/BGA/CSP/WLCSP) + thermal-spec defaults |
| `eng-web.noc` | `ip_generate_noc` | NoC topology string -> config (mesh/ring/crossbar) + defaults |
| `eng-web.coverage` | `verify_coverage_report` | Coverage aggregate stats (total/hit -> pct, uncovered) |
| `eng-web.floorplan` | `pnr_auto_floorplan` | Block-input normalization + die-sizing heuristic (sqrt(area * 1.5)) |
| `eng-web.ir-drop` | `power_analyze_ir_drop` | Uniform interior-current grid builder |
| `eng-web.dft` | `dft_insert_scan`/`dft_generate_atpg` | Scan-chain config + FF-name/fault-list synthesis |
| `eng-web.cam` | `cam_generate_gcode` | Tool/stock/pocket-op/gcode-config defaults |

**Excluded entirely** (native-only / delegates to unported crates, no
portable logic of its own): every `#[wasm_bindgen]` export's actual
computation (schematic/ERC/gerber, B-rep/tessellation/STEP, toolpath
generation, Verilog parse/simulate/VCD, FEA meshing/materials, SPICE MNA
solve, PDK tech-file/stdcell/memory compile, floorplan placement/GDSII
export, scan-chain insertion/ATPG pattern generation, equivalence
checking, dynamic-power/IR-drop solve, transmission-line Z0/eye-diagram
calc, package/thermal estimation math, Monte Carlo yield run/PVT corners,
NoC router/link synthesis, CDC analysis, the P10 signoff flow), the
`eng_sdk_version` version-string passthrough, and `test-visual.html`
(pure browser-canvas demo harness, not source logic).

## Status

Restored (scoped) — 17 tests / 49 assertions, 0 failures (the original had
no `#[test]`s in `lib.rs`; these provide coverage of the ported kernels).

## Develop

```bash
kbb -M:test
```
