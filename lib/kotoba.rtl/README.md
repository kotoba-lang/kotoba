# kotoba-lang/rtl

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-rtl`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

HDL editor (Verilog/VHDL parsing), event-driven simulation, waveform
viewer, and synthesis netlist.

| Namespace | Restored from | Purpose |
|---|---|---|
| `rtl.hdl` | `hdl` | Verilog/VHDL AST (plain EDN maps/keywords) + minimal Verilog module-header parser |
| `rtl.simulator` | `simulator` | Event-driven RTL simulator, four-valued IEEE 1164 logic, delta-cycle support |
| `rtl.waveform` | `waveform` | Waveform view + IEEE 1364 VCD (Value Change Dump) export |
| `rtl.synthesis` | `synthesis` | Gate-level netlist, memoized combinational-depth estimation, constant-folding optimization |
| `rtl.eda-adapter` | new | Converts a `rtl.synthesis` gate-netlist into a `kotoba-lang/eda` static-timing-analysis job |
| `rtl.vhdl-adapter` | new | Converts an `org-ieee-vhdl` entity/architecture into an `rtl.hdl` module/port, so VHDL sources drive the same pipeline as Verilog |

Depends on `kotoba-lang/{engineer,engineer-render}` for shared contracts, on
`kotoba-lang/eda` (`:local/root "../eda"`) for `rtl.eda-adapter`, and on
`kotoba-lang/org-ieee-vhdl` (`:local/root "../org-ieee-vhdl"`) for
`rtl.vhdl-adapter`.

## Status

Restored — all 4 modules ported from the original 891-line Rust `lib.rs`,
with all 5 original Rust unit tests mirrored 1:1 in `test/rtl_test.cljk`
(+1 smoke test). Pure data + pure functions/parsers throughout; no IO/GPU.
`rtl.simulator`'s event queue uses a sorted vector (kept sorted on insert)
rather than a literal binary heap — same externally observable ordering
as the original's `BinaryHeap<SimEvent>` min-heap.

## RTL synthesis -> static timing analysis (`rtl.eda-adapter`)

`rtl.eda-adapter` drives [`kotoba-lang/eda`](https://github.com/kotoba-lang/eda)'s
`kotoba.eda.core/analyze-timing` from a `rtl.synthesis` gate-netlist, closing
the "synthesize RTL to gates, then run static timing analysis" loop.

Connectivity scope, stated honestly: a `rtl.synthesis/gate` DOES carry real
connectivity — `{:gate-type t :inputs [net-name ...] :output net-name}` — and
a gate-netlist's `:primary-inputs`/`:primary-outputs` are net names in the
same namespace. So `netlist->timing-edges` builds a REAL per-gate
delay-annotated timing graph from that connectivity (one edge per
`input-net -> gate-output-net`, taken straight from each gate's own
`:inputs`/`:output`) — this is not a fabricated graph and not a serial
worst-case-chain approximation.

What IS approximated, and said plainly:

- **Delay model**: `rtl.synthesis` carries no physical delay data (no
  liberty/LEF timing arcs — that would come from a later
  `org-synopsys-liberty`/`org-si2-lef` integration, out of scope here).
  `default-delay-model` is a flat per-gate-type nanosecond constant
  (`{:and 0.1 :or 0.1 :not 0.05 :dff 0.2 ... :default 0.15}`), not real cell
  timing.
- **Sequential (`:dff`) boundary**: mirrors `rtl.synthesis/estimate-depth`'s
  own convention of resetting combinational depth to 0 at every `:dff` (a
  register launches a fresh stage each clock edge rather than
  combinationally forwarding D into Q within the same period). A DFF's Q net
  gets a single edge from a synthetic zero-arrival `clock-launch` node
  (delay = the `:dff` entry of the delay model, i.e. clock-to-Q), and its D
  input net is added to `:eda.timing/endpoints` as a register setup check,
  alongside the netlist's `:primary-outputs`. This is a single-cycle,
  single-clock-domain approximation — it does not unroll multi-cycle
  register-to-register paths.

```clojure
(require '[rtl.synthesis :as synthesis]
         '[rtl.eda-adapter :as eda-adapter])

(def netlist
  (-> (synthesis/gate-netlist)
      (assoc :primary-inputs ["a" "b"] :primary-outputs ["out"])
      (update :gates conj
              (synthesis/gate :and ["a" "b"] "n1")
              (synthesis/gate :not ["n1"] "out"))))

(eda-adapter/analyze-netlist-timing netlist {:clock-period-ns 5.0})
;; => {:eda.signoff/type :signoff/timing-pvt :eda.signoff/status :passed ...}
```

Same alpha/prototype-grade maturity level as `kotoba-lang/eda` itself — see
that repo's README coverage table.

## VHDL frontend (`rtl.vhdl-adapter`)

`rtl.hdl/parse-verilog` is Verilog-only. `rtl.vhdl-adapter` gives `rtl` a
second frontend by converting [`kotoba-lang/org-ieee-vhdl`](https://github.com/kotoba-lang/org-ieee-vhdl)'s
independent entity/architecture model (IEEE 1076 §3.2/§3.3) into the same
`rtl.hdl/rtl-module`/`rtl-port` shape `parse-verilog` builds towards — so a
VHDL source can drive the exact same synthesis/simulation/eda-timing
pipeline as a Verilog one, through one uniform module representation.

`parse-vhdl-source` mirrors `parse-verilog`'s API shape: `[:ok rtl-module]`
on success, `[:error msg]` on failure (missing `entity` declaration or
missing `end entity`), so callers don't need to branch on which HDL
frontend produced the module they're holding.

Direction mapping: VHDL's 4 port modes (`:in`/`:out`/`:inout`/`:buffer`)
don't line up 1:1 with `rtl.hdl/port-directions`' 3-way scheme (`:input`/
`:output`/`:inout`). `:in`/`:out`/`:inout` map directly; `:buffer` collapses
to `:output` — a buffer port is still single-driver (driven only by this
entity) exactly like `:out`, the only VHDL-specific wrinkle (its driven
value may be read back inside the architecture) has no synthesis-pin-
direction meaning, so it is not treated as `:inout`.

Width comes from `vhdl.entity/bus-width`, which already parses vector types
(`"std_logic_vector(7 downto 0)"` -> 8) and treats scalar types with no
range (`std_logic`, `boolean`, ...) as width 1.

```clojure
(require '[rtl.vhdl-adapter :as vhdl-adapter])

(vhdl-adapter/parse-vhdl-source
 "entity and_gate is
    port (
      a : in std_logic;
      b : in std_logic;
      y : out std_logic;
    );
  end entity;")
;; => [:ok {:name "and_gate"
;;          :ports [{:name "a" :direction :input :width 1 :signal-type :logic}
;;                   {:name "b" :direction :input :width 1 :signal-type :logic}
;;                   {:name "y" :direction :output :width 1 :signal-type :logic}]
;;          :parameters [] :instances [] :always-blocks [] :assigns []}]
```

`architecture->process-count` exposes a small piece of `vhdl.architecture`-
derived info for synthesis-style reporting: given an architecture body's
`:processes`, it returns `{:combinational n :sequential m}` using
`vhdl.architecture/combinational?`'s clock-sensitivity heuristic.

## Develop

```bash
kbb -M:test
```
