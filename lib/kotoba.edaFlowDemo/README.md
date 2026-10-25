# kotoba-lang/eda-flow-demo

A reference/demo repo, not a new capability: it proves that the
kotoba-lang semiconductor/EDA repo family's cross-repo wiring --
`rtl` -> `eda` -> `pnr` <- `pdk`, `signal-integrity` <- `org-ibis`,
`org-accellera-uvm` -> `rtl` -- genuinely composes end to end, on one
concrete circuit, rather than being individually tested in isolation and
never actually run together. Every wiring point below was already real
and already tested in its own repo before this demo existed; what this
repo adds is a single, honest, runnable trace through all of them at once,
with real assertions at every stage (not just "it didn't throw").

## The circuit

A **2-bit synchronous binary up-counter**: `q0' = !q0`, `q1' = q0 xor q1`
-- the standard toggle-flip-flop identity for a ripple-carry-free
synchronous counter. Chosen because it's small enough to hand-author
correctly gate-by-gate (1 NOT, 1 XOR, 2 DFFs) while still exercising the
DFF-aware paths that make this family's wiring interesting: `rtl.eda-
adapter`'s clock-launch/setup-endpoint handling for STA, and `pnr.upf-
adapter`'s domain-crossing checks between a combinational power domain and
a sequential one.

## An honest boundary: `rtl.hdl` is header-only

`rtl.hdl/parse-verilog` and `rtl.vhdl-adapter/parse-vhdl-source` extract a
module/entity name and its port list (name/direction/width) -- nothing
more. Neither has any notion of `always`/`process` block *behaviour*, so
there is no Verilog/VHDL text in this repo whose body describes `!q0` or
`q0 xor q1` and gets compiled into gates -- that capability doesn't exist
in `rtl.hdl` (see its own docstring: "Intentionally minimal -- handles the
common Verilog-2001 module header pattern only"). Stage 1 and stage 2 are
therefore deliberately independent in this demo: stage 1 proves the header
parse works on real HDL text for this circuit's port list (two frontends:
Verilog's scalar `q0`/`q1` vs VHDL's `std_logic_vector(1 downto 0)` bus
`q`), and stage 2's gate netlist is hand-built directly via
`rtl.synthesis`'s gate/netlist constructors. Every stage from 2 onward
operates on the hand-built netlist, not on stage 1's parse result.

## Stages

| # | Stage | Sibling repo(s) used | What's asserted |
|---|-------|----------------------|------------------|
| 1 | RTL parse (both frontends) | `rtl` (`rtl.hdl`, `rtl.vhdl-adapter`) | Verilog header yields `["counter2" ["clk" "rst" "q0" "q1"]]`; VHDL entity yields typed ports incl. a 2-bit `q` bus |
| 2 | Gate synthesis (hand-built) | `rtl` (`rtl.synthesis`) | 4 gates (NOT/XOR/2xDFF) with real feedback connectivity (`q0`/`q1` are both DFF outputs and NOT/XOR inputs); `stats` = `{:gate-count 4 :lut-count 2 :ff-count 2 :estimated-max-freq-mhz 1000.0}` |
| 3 | SDC-constrained timing signoff | `rtl` (`rtl.eda-adapter`), `org-synopsys-sdc` (via `kotoba.eda.sdc-adapter`), `eda` (`kotoba.eda.core`) | `create_clock -period 1.0` genuinely parsed and used (not a hardcoded default); worst path launch->DFF->XOR = 0.32ns, slack = 0.68ns, status `:passed`; a second, tighter-clock SDC script (0.1ns) genuinely fails signoff (negative slack) |
| 4 | Cell library | `org-si2-lef` (`lef.core`), `pdk` (`pdk.stdcell`, `pdk.technology`, independent sanity check only) | 3 real LEF macros (INVX1/XOR2X1/DFFX1) with real SIZE + pin geometry parsed; `pdk.stdcell/create-generic-lib` independently produces its documented ~20-cell (21 exactly) library; `pdk.technology/for-node` produces a 9-metal-layer tech file for `:n45` |
| 5 | Placement | `pnr` (`pnr.placement`, `pnr.lef-adapter`) | Each cell's `:width-sites` resolved from the LEF macro's real SIZE (3/8/11/11, not hand-picked); greedy placement spills both DFFs into their own rows; `placement-stats` (4 cells, real utilization/HPWL) |
| 6 | Routing | `pnr` (`pnr.routing`) | The NOT gate's `Y` output -> DFF0's `D` input (a real connection from stage 2) routes successfully between the two cells' real LEF pin centers; 1 routed net, 0 overflow, positive wire length |
| 7 | Export (GDSII / DEF / OpenAccess) | `pnr` (`pnr.lef-adapter`+`pnr.gdsii`, `pnr.def-adapter`, `pnr.openaccess-adapter`) | GDSII: valid header stream + correct boundary-element count; DEF: 4 PLACED components with real scaled microns + orientations; OpenAccess: 11 flattened shapes, all well-formed; **a dedicated orientation-math probe proves `design->flat-shapes` applies a real MX (mirror-about-X) transform** for a non-R0 cell, hand-computed independently and shown to differ from what translate-only (GDSII-path-style) geometry would give |
| 8 | UPF power intent | `pnr` (`pnr.upf-adapter`, `pnr.floorplan`), `org-ieee-upf` (`upf.domain`) | The real placement validates with **zero** violations against two power domains (`PD_A` combinational / `PD_B` sequential) matching its two floorplan blocks; a deliberately misassigned variant (DFF0 relabeled into the wrong domain while staying in the same physical block) is correctly **caught** as exactly one violation -- a real negative test, not just a happy path |
| 9 | Signal integrity | `org-ibis` (`ibis.model`), `signal-integrity` (`signal-integrity.ibis-adapter`) | Amplitude (1800mV) and rise time (600ps) genuinely derived from a real IBIS V-I table + ramp rate, not hand-picked; eye-diagram metrics are structurally sane (height >= 0, width within the bit period, jitter passed through, BER in `[0,1]`) |
| 10 | Verification | `org-accellera-uvm` (`uvm.rtl-driver`), `rtl` (`rtl.simulator`) | A UVM-style driver/monitor pair genuinely drives + observes `q0` (one of this circuit's own nets) through a real `rtl.simulator` instance; the monitor's observed history matches exactly what the driver applied |

## Structure

- `src/eda_flow_demo/flow.cljk` -- one namespace, one function per stage
  (`stage-1-parse-verilog`, `stage-2-synthesize`, ... `stage-10-
  verification`), plus `run-full-flow` threading the whole pipeline and
  returning every stage's result keyed by stage name.
- `test/eda_flow_demo/flow_test.cljk` -- one `deftest` per stage (reusing
  the exact fixtures `run-full-flow` uses) asserting that stage's specific
  output, plus `full-flow-runs-end-to-end` calling `run-full-flow` once and
  checking every stage key is present and well-formed.

**18 tests / 92 assertions, 0 failures.**

## Dependency graph

`deps.edn` declares `:local/root` on the 9 sibling repos this namespace
directly `:require`s: `rtl`, `eda`, `pdk`, `pnr`, `org-si2-lef`,
`org-ieee-upf`, `org-ibis`, `signal-integrity`, `org-accellera-uvm`.
Everything else this pipeline touches (`org-synopsys-sdc`, `org-ieee-vhdl`,
`org-si2-def`, `org-si2-openaccess`, `org-synopsys-liberty`,
`org-ieee-systemverilog`) comes in transitively through those 9 repos'
own `deps.edn` (`kbb -Spath` resolves the whole 15-repo graph cleanly,
one `clojure` jar version selected, no coordinate conflicts -- the largest
dependency fan-in of any repo in this family so far).

## Develop

```bash
kbb -M:test   # 18 tests / 92 assertions, 0 failures
kbb -Spath    # confirms the full transitive local/root graph resolves
kbb -M:lint   # clj-kondo, 0 errors/warnings
```
