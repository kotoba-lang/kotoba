# kotoba-lang/pcb

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-eda`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI EDA: schematic capture, PCB layout, netlist/BOM generation, ERC/DRC
validation.

**Named `pcb`, not `eda`** — `kotoba-lang/eda` already exists as an
unrelated, mature repo (OpenSTA-class timing/PVT slack analysis +
OpenROAD-class grid routing/overflow checks, its own docs site + evidence
output design). This repo restores the legacy `kami-eda` schematic/PCB
tool under a collision-free name.

| Namespace | Restored from | Purpose |
|---|---|---|
| `pcb.schematic` | `schematic` | Symbol placement, wire routing, net labelling, netlist extraction |
| `pcb.layout` | `pcb` | Footprint placement, trace routing, vias, copper zone pours, DRC (named `pcb.layout` not `pcb.pcb` — parent namespace is already `pcb`) |
| `pcb.netlist` | `netlist` | SPICE/Verilog-gate-level/EDIF export (all 3 fully implemented) + BOM generation |
| `pcb.erc` | `erc` | Electrical Rule Check — 5 rules (unconnected pin, output conflict, undriven power, single-pin net, duplicate designator) |
| `pcb.route` | *(new, not a restoration)* | Grid-based maze autorouting (Lee's algorithm) — turns a net's placed pads into an actual DRC-clean trace, see below |

Violations are plain maps matching `kotoba-lang/engineer`'s
`engineer.drc` violation shape (`{:rule-id :severity :message :entity-ids
:location}`). Depends on `kotoba-lang/engineer` for shared contracts.

## Status

Restored — all 4 modules ported from the original 1031-line Rust
`lib.rs`, with all 7 original Rust unit tests mirrored 1:1 in
`test/pcb_test.cljk` (+1 smoke test, +4 netlist-export tests) — 12
tests / 28 assertions, 0 failures. Pure data + pure functions
throughout; no IO/GPU. `pcb.layout/run-drc`'s `fmt3` helper is
reader-conditional (`String/format` on JVM, `.toFixed` on CLJS) for
full portability.

`pcb.netlist/export-netlist` now fully implements all 3 formats (no
stubs): `:spice`, `:verilog-gate-level`, and `:edif` all resolve real
symbol/pin/net connectivity via the shared `find-net-name` helper —
Verilog emits a `module`/`endmodule` block with one instantiation per
symbol and a named port connection per pin; EDIF emits a `(cell top
(view netlist ...))` with `(instance ...)` per symbol and `(net ...)`
per connected net carrying real `(portRef ... (instanceRef ...))`
pairs. Port/portRef labels use the pin's own `:name` when present
(e.g. `.B`/`.E` for a transistor), falling back to `p<number>` for
pins with no name. Known limitations: every pin is a scalar 1-bit
connection (no bus/vector nets or multi-bit ports), and everything
flattens into a single top-level module/cell (no hierarchical
sub-modules/sub-cells).

`pcb.route` (new, `test/pcb_route_test.cljk`) adds 11 tests / 33
assertions on top of the above — repo total 23 tests / 61 assertions, 0
failures. Includes a specifically-constructed obstacle-detour test
(genuine 28.5mm routed path vs. the 16.0mm unobstructed Manhattan
minimum between the same two pads, DRC-clean) and a boxed-in-net
failure case (`:unrouted`, layout left unchanged) — not just the happy
path.

## Routing (`pcb.route`)

Before this, `pcb.layout/route-trace` was a pure data constructor — it
recorded whatever `:points` you handed it, with no pathfinding. Nothing
in the repo actually computed a route. `pcb.route/route-net` does:

- **Lee's algorithm** (C. Y. Lee, 1961) — breadth-first wave propagation
  over a grid from a source cell, tracing back the shortest
  obstacle-avoiding 4-connected path once the target is reached. The
  textbook maze-routing algorithm every PCB autorouter historically
  started from.
- **Multi-pin nets** are joined with a Manhattan-distance minimum
  spanning tree (Prim's algorithm) over the net's pads, then each MST
  edge is maze-routed independently — an approximation, not a true
  rectilinear Steiner tree.
- **Obstacles** are every other net's pads (own physical extent from
  `:size`, not just their center point, plus DRC clearance), traces,
  vias, and a 1-cell board-edge border. `route-all` routes nets in
  ascending net-id order, so an earlier net's trace becomes an obstacle
  for a later one.

Honest scope — what this is *not*:

- **Single-layer only.** No via insertion to escape a fully boxed-in
  net; a real autorouter falls back to another layer, this one just
  reports that net as `:unrouted` (see `route-all`'s `:failed`).
- **Grid-quantized, 4-connected paths** (default 0.25mm pitch), not the
  45°/arc corner styles a production tool applies as a post-process.
- **Sequential, not simultaneous** — no rip-up-and-reroute. Routing
  order can determine whether a later net finds a path at all.
- **Circumscribing-circle pad clearance**, not exact rect/oblong
  footprints — exact for round pads, a safe but conservative
  over-estimate for rect/oblong ones.

```clojure
(require '[pcb.layout :as layout] '[pcb.route :as route])
(def board (layout/pcb-board [[0.0 0.0] [20.0 20.0]] [(layout/layer-def :front "F.Cu" 0.035)]))
(def pad-a (layout/pad {:center [0 0] :size [1 1] :shape :round :drill nil :layers [:front] :net-id 1}))
(def pad-b (layout/pad {:center [0 0] :size [1 1] :shape :round :drill nil :layers [:front] :net-id 1}))
(let [[_ lay] (layout/place-footprint (layout/pcb-layout board) "R" "R1" 2.0 10.0 0 :front [pad-a])
      [_ lay] (layout/place-footprint lay "R" "R2" 18.0 10.0 0 :front [pad-b])
      result (route/route-all lay)]
  result) ; => {:layout ... :routed [1] :failed []}
```

## Develop

```bash
kbb -M:test
kbb -M:lint
```
