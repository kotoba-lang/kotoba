(ns eda-flow-demo.flow
  "End-to-end reference flow tying together the kotoba-lang semiconductor/EDA
  repo family on ONE concrete circuit: a 2-bit synchronous binary up-counter
  (`q1 q0`, free-running, no external data inputs -- `q0' = !q0`,
  `q1' = q0 xor q1`, the standard ripple-carry-free synchronous counter
  identity). Chosen because it needs exactly one XOR, one NOT, and two DFFs
  -- small enough to hand-author correctly gate-by-gate, but real enough to
  exercise the DFF-aware paths of `rtl.eda-adapter` (STA endpoints/launch
  edges) and `pnr.upf-adapter` (two power domains: combinational vs
  sequential) without inventing behaviour the underlying libraries don't
  actually have.

  ## The `rtl.hdl` boundary (read this before trusting stage 1)

  `rtl.hdl/parse-verilog` and `rtl.vhdl-adapter/parse-vhdl-source` are
  genuinely HEADER-ONLY: they extract a module/entity name and its port
  list (name/direction/width), nothing more. Neither parser has any notion
  of `always`/`process` block *behaviour* -- there is no Verilog/VHDL
  text anywhere in this repo whose body describes '!q0' or 'q0 xor q1' and
  gets compiled into gates. So stage 1 (`stage-1-parse-verilog` /
  `stage-1-parse-vhdl`) and stage 2 (`stage-2-synthesize`) are DELIBERATELY
  independent of each other in this demo: stage 1 proves the header parse
  works on real HDL text for this circuit's port list (two ways -- Verilog
  scalar ports `q0`/`q1` vs a VHDL `std_logic_vector(1 downto 0)` bus `q`,
  both legitimate descriptions of the same 2-bit interface), and stage 2's
  gate netlist is hand-built directly via `rtl.synthesis`'s gate/netlist
  constructors -- NOT derived from parsing the HDL body, because that
  capability doesn't exist. Every stage from 2 onward operates on the
  hand-built gate netlist, not on stage 1's parse result. This is not a
  cut corner hidden from the reader; it is the honest shape of what
  `rtl.hdl` actually restores from kami-rtl (see that namespace's own
  docstring: 'Intentionally minimal -- handles the common Verilog-2001
  module header pattern only.')."
  (:require [rtl.hdl :as hdl]
            [rtl.vhdl-adapter :as vhdl-adapter]
            [rtl.synthesis :as synth]
            [rtl.eda-adapter :as eda-adapter]
            [rtl.simulator :as rtl-sim]
            [kotoba.eda.sdc-adapter :as sdc-adapter]
            [lef.core :as lef]
            [pdk.stdcell :as stdcell]
            [pdk.technology :as technology]
            [pnr.placement :as placement]
            [pnr.routing :as routing]
            [pnr.lef-adapter :as lef-adapter]
            [pnr.gdsii :as gdsii]
            [pnr.def-adapter :as def-adapter]
            [pnr.upf-adapter :as upf-adapter]
            [pnr.openaccess-adapter :as oa-adapter]
            [pnr.floorplan :as floorplan]
            [upf.domain :as upf-domain]
            [ibis.model :as ibis]
            [signal-integrity.ibis-adapter :as si-adapter]
            [uvm.rtl-driver :as uvm-driver]))

;; ---------------------------------------------------------------------------
;; Stage 1 -- RTL parse (header-only, both frontends; see namespace docstring)
;; ---------------------------------------------------------------------------

(def verilog-src
  "module counter2(clk, rst, q0, q1);\nendmodule\n")

(def vhdl-src
  ;; NOTE: every port line needs its own trailing `;`, including the last one
  ;; before the closing `);` -- `vhdl.parser/parse-entity`'s `port-decl-re`
  ;; requires it (`^(\S+)\s*:\s*(in|out|inout|buffer)\s+([^;]+);`); a `q`
  ;; line without it silently fails to match and the port is dropped.
  "entity counter2 is\n  port (\n    clk : in std_logic;\n    rst : in std_logic;\n    q   : out std_logic_vector(1 downto 0);\n  );\nend entity counter2;\n")

(defn stage-1-parse-verilog
  "Header-only Verilog parse of `verilog-src` via `rtl.hdl/parse-verilog`:
  module name + flat port-name list (no direction/width -- that parser
  doesn't extract it)."
  []
  (hdl/parse-verilog verilog-src))

(defn stage-1-parse-vhdl
  "VHDL entity parse of `vhdl-src` via `rtl.vhdl-adapter/parse-vhdl-source`:
  richer than the Verilog path (direction + bit-width per port), because
  `org-ieee-vhdl`'s entity parser already extracts port mode/type and this
  adapter converts that into an `rtl.hdl/rtl-module`. Same circuit's
  interface, described the VHDL way -- q as one 2-bit bus instead of two
  scalar ports."
  []
  (vhdl-adapter/parse-vhdl-source vhdl-src))

;; ---------------------------------------------------------------------------
;; Stage 2 -- gate-level synthesis (hand-built; see namespace docstring)
;; ---------------------------------------------------------------------------

(defn build-gate-netlist
  "The 2-bit counter's gate netlist, hand-built via `rtl.synthesis`'s
  constructors directly:

    n0 = NOT(q0)        -- next-state of bit 0 (always toggles)
    n1 = XOR(q0, q1)    -- next-state of bit 1 (toggles when q0 was 1)
    q0 = DFF(n0)        -- bit 0 register
    q1 = DFF(n1)        -- bit 1 register

  `q0`/`q1` are simultaneously gate outputs (of the DFFs) and gate inputs
  (of the NOT/XOR feeding them back) -- the real combinational feedback
  loop that makes this a counter, not a fabricated net name. No
  `:primary-inputs` (a free-running counter has no external data input in
  this simplified model; clock/reset are outside `rtl.synthesis`'s
  gate-level vocabulary, same boundary as `rtl.eda-adapter`'s synthetic
  clock-launch node)."
  []
  (-> (synth/gate-netlist)
      (update :gates conj
              (synth/gate :not ["q0"] "n0")
              (synth/gate :xor ["q0" "q1"] "n1")
              (synth/gate :dff ["n0"] "q0")
              (synth/gate :dff ["n1"] "q1"))
      (assoc :primary-outputs ["q0" "q1"])))

(defn stage-2-synthesize
  "The netlist plus `rtl.synthesis/stats` (gate/LUT/FF counts, naive
  max-frequency estimate)."
  []
  (let [netlist (build-gate-netlist)]
    {:netlist netlist :stats (synth/stats netlist)}))

;; ---------------------------------------------------------------------------
;; Stage 3 -- SDC-constrained timing signoff
;; (rtl.eda-adapter's node/edge/endpoint graph + org-synopsys-sdc's parsed
;;  clock period, via kotoba.eda.sdc-adapter, resolved by kotoba.eda.core)
;; ---------------------------------------------------------------------------

(def sdc-script
  "create_clock -name clk -period 1.0 -waveform {0.0 0.5} [get_ports clk]\n")

(defn stage-3-timing-signoff
  "Builds a `kotoba.eda.core/analyze-timing`-ready base job from `netlist`
  using `rtl.eda-adapter`'s real per-gate connectivity (nodes/edges/
  endpoints derived straight from the netlist's own net names -- not a
  fabricated graph), then hands it to
  `kotoba.eda.sdc-adapter/analyze-timing-from-sdc`, which parses
  `sdc-script-text` (via `org-synopsys-sdc`'s `sdc.parser`) for its
  `create_clock -period`, merges that into the job as
  `:eda.timing/clock-period-ns`, and runs `kotoba.eda.core/analyze-timing`.
  Three separately-owned repos (rtl, org-synopsys-sdc, eda) composed for
  one signoff evidence map."
  [netlist sdc-script-text]
  (let [base-job {:eda.job/tool :sw/opensta
                  :eda.job/operation :op/analyze-timing
                  :eda.timing/corners eda-adapter/default-corners
                  :eda.timing/nodes (eda-adapter/netlist->timing-nodes netlist)
                  :eda.timing/edges (eda-adapter/netlist->timing-edges netlist)
                  :eda.timing/endpoints (eda-adapter/netlist->timing-endpoints netlist)}]
    (sdc-adapter/analyze-timing-from-sdc sdc-script-text base-job)))

;; ---------------------------------------------------------------------------
;; Stage 4 -- cell library (concrete LEF macros for stages 5-7 + a pdk
;; generic-library-generator sanity check, kept separate since pdk.stdcell's
;; cells carry no physical geometry and can't feed placement/export)
;; ---------------------------------------------------------------------------

(def lef-text
  "A small, hand-authored LEF library with real pin geometry for exactly
  the 3 standard cells this circuit's netlist needs: an inverter (for the
  NOT gate), a 2-input XOR, and a D flip-flop (for both DFFs -- a real
  library reuses one DFF cell for many register bits, same as here)."
  "
MACRO INVX1
  CLASS CORE ;
  SIZE 0.5 BY 1.4 ;
  SYMMETRY X Y ;
  SITE core_site ;
  PIN A
    DIRECTION INPUT ;
    PORT
      LAYER metal1 ;
        RECT 0.0 0.5 0.1 0.9 ;
    END
  END A
  PIN Y
    DIRECTION OUTPUT ;
    PORT
      LAYER metal1 ;
        RECT 0.4 0.5 0.5 0.9 ;
    END
  END Y
END INVX1
MACRO XOR2X1
  CLASS CORE ;
  SIZE 1.6 BY 1.4 ;
  SYMMETRY X Y ;
  SITE core_site ;
  PIN A
    DIRECTION INPUT ;
    PORT
      LAYER metal1 ;
        RECT 0.0 0.5 0.1 0.9 ;
    END
  END A
  PIN B
    DIRECTION INPUT ;
    PORT
      LAYER metal1 ;
        RECT 0.3 0.5 0.4 0.9 ;
    END
  END B
  PIN Y
    DIRECTION OUTPUT ;
    PORT
      LAYER metal1 ;
        RECT 1.5 0.5 1.6 0.9 ;
    END
  END Y
END XOR2X1
MACRO DFFX1
  CLASS CORE ;
  SIZE 2.2 BY 1.4 ;
  SYMMETRY X Y ;
  SITE core_site ;
  PIN D
    DIRECTION INPUT ;
    PORT
      LAYER metal1 ;
        RECT 0.0 0.5 0.1 0.9 ;
    END
  END D
  PIN CK
    DIRECTION INPUT ;
    PORT
      LAYER metal1 ;
        RECT 0.3 0.0 0.4 0.2 ;
    END
  END CK
  PIN Q
    DIRECTION OUTPUT ;
    PORT
      LAYER metal1 ;
        RECT 2.1 0.5 2.2 0.9 ;
    END
  END Q
END DFFX1
")

(def tech-node :n45)

(defn stage-4-cell-library
  "Parses `lef-text` via `org-si2-lef`'s `lef.core/parse-lef` -- this is
  the library stages 5-7 actually place/export, since it carries real
  `:size`/pin-rect geometry `pnr.lef-adapter`/`pnr.openaccess-adapter`
  need. Also runs `pdk.stdcell/create-generic-lib` + `pdk.technology/
  for-node` for `tech-node` as an independent sanity check that `pdk`'s
  own ~20-cell generic-library generator and tech-file generator work --
  NOT used downstream (`pdk.stdcell`'s cells carry no `:size`/pin
  geometry, so they can't resolve a placement site-width the way a real
  LEF macro can; see `pdk.lef`, which is itself just a facade over
  `org-si2-lef`)."
  []
  (let [[status lib] (lef/parse-lef lef-text)
        stdlib (stdcell/create-generic-lib tech-node)
        tech-file (technology/for-node tech-node)]
    {:status status :lib lib :stdcell-lib stdlib :tech-file tech-file}))

;; ---------------------------------------------------------------------------
;; Stage 5 -- placement
;; ---------------------------------------------------------------------------

(def site-width-um 0.2)
(def site-height-um 1.4)

(def not1-instance "top/pdA/u_not1")
(def xor1-instance "top/pdA/u_xor1")
(def dff0-instance "top/pdB/u_dff0")
(def dff1-instance "top/pdB/u_dff1")

(defn build-rows
  "3 rows, each 12 sites wide at `site-width-um`/`site-height-um` --
  row0 fits NOT (3 sites) + XOR2 (8 sites) = 11/12; the 11-site DFF
  overflows row0, so DFF0 lands in row1 (odd -> `:fs` orientation) and
  DFF1 overflows again into row2 (even -> `:n`) -- deliberately sized so
  at least one placed cell (DFF0) gets a non-identity orientation,
  needed for stage 7's OpenAccess orientation-math proof."
  []
  [(placement/placement-row {:y 0.0 :height site-height-um :site-width site-width-um :num-sites 12})
   (placement/placement-row {:y 1.4 :height site-height-um :site-width site-width-um :num-sites 12})
   (placement/placement-row {:y 2.8 :height site-height-um :site-width site-width-um :num-sites 12})])

(defn stage-5-placement
  "Resolves each netlist gate to a placement cell via
  `pnr.lef-adapter/netlist-cell-from-lef` (real LEF `:size` -> site
  width, not a hand-picked integer), places them via
  `pnr.placement/place-cells`, and computes `placement-stats`."
  [lef-lib]
  (let [netlist-cells [(lef-adapter/netlist-cell-from-lef lef-lib "INVX1" not1-instance site-width-um)
                        (lef-adapter/netlist-cell-from-lef lef-lib "XOR2X1" xor1-instance site-width-um)
                        (lef-adapter/netlist-cell-from-lef lef-lib "DFFX1" dff0-instance site-width-um)
                        (lef-adapter/netlist-cell-from-lef lef-lib "DFFX1" dff1-instance site-width-um)]
        rows (build-rows)
        placed (placement/place-cells netlist-cells rows)
        stats (placement/placement-stats placed)]
    {:netlist-cells netlist-cells :placement placed :stats stats}))

;; ---------------------------------------------------------------------------
;; Stage 6 -- routing (one real net between two placed cells' real LEF pins)
;; ---------------------------------------------------------------------------

(defn- pin-local-center
  "Center point `[x y]` (microns, macro-local) of `pin-name`'s first PORT
  rect on `macro` (an `org-si2-lef` macro map)."
  [macro pin-name]
  (let [pin (some #(when (= pin-name (:name %)) %) (:pins macro))
        [x1 y1 x2 y2] (:rect (first (:port pin)))]
    [(/ (+ x1 x2) 2.0) (/ (+ y1 y2) 2.0)]))

(defn- placed-pin-abs
  "Absolute `[x y]` (microns) of `pin-name` on `placed-cell`, given its
  LEF `macro` and the `placement-row` it landed in (for the row's real
  `:y`)."
  [macro row placed-cell pin-name]
  (let [[lx ly] (pin-local-center macro pin-name)]
    [(+ (:x placed-cell) lx) (+ (:y row) ly)]))

(defn- abs->grid [x-pitch y-pitch [ax ay]]
  [(long (Math/round (/ (double ax) x-pitch)))
   (long (Math/round (/ (double ay) y-pitch)))])

(def routing-x-pitch 0.2)
(def routing-y-pitch 0.2)

(defn stage-6-routing
  "Routes net `n0` (NOT gate's `Y` output -> DFF0's `D` input -- a real
  connection in `build-gate-netlist`) between its two placed cells' real
  LEF pin centers, converted to routing-grid coordinates at
  `routing-x-pitch`/`routing-y-pitch`, via `pnr.routing`'s Lee/BFS maze
  router."
  [lef-lib {:keys [placement]}]
  (let [rows (:rows placement)
        not1 (first (:cells placement))
        dff0 (nth (:cells placement) 2)
        not1-macro (lef/find-macro lef-lib "INVX1")
        dff0-macro (lef/find-macro lef-lib "DFFX1")
        src-abs (placed-pin-abs not1-macro (nth rows (:row-idx not1)) not1 "Y")
        dst-abs (placed-pin-abs dff0-macro (nth rows (:row-idx dff0)) dff0 "D")
        [sx sy] (abs->grid routing-x-pitch routing-y-pitch src-abs)
        [dx dy] (abs->grid routing-x-pitch routing-y-pitch dst-abs)
        grid (routing/routing-grid {:layers ["metal1" "metal2"]
                                     :x-pitch routing-x-pitch :y-pitch routing-y-pitch
                                     :num-x 30 :num-y 20})
        rtr0 (routing/router grid)
        [rtr net] (routing/route-net rtr0 "n0" [[0 sx sy] [0 dx dy]])
        stats (routing/routing-stats rtr)]
    {:src [0 sx sy] :dst [0 dx dy] :net net :router rtr :stats stats}))

;; ---------------------------------------------------------------------------
;; Stage 7 -- 3-way export: GDSII, DEF, OpenAccess
;; ---------------------------------------------------------------------------

(def die-width-um 5.0)
(def die-height-um 4.2)

(def export-x-scale-um
  "The width-axis scale factor passed to `pnr.lef-adapter/
  design->gdsii-structure` / `pnr.def-adapter/placement->def-design`.
  Deliberately `1.0`, NOT `site-width-um` -- `build-rows` already gives its
  placement rows a real-micron `:site-width` (`site-width-um`), so
  `pnr.placement/place-cells`' output `:x` (site-cursor * row's
  `:site-width`) already IS a real-micron x-coordinate (see stage 5/6/8,
  which all read `:x` directly as microns for routing/UPF). Both export
  adapters independently multiply `:x` by whatever width-scale they're
  given (their own documented contract, tuned for callers whose placement
  rows use an abstract `:site-width 1.0` and want the adapter to do the
  micron conversion) -- passing the real `site-width-um` here again would
  double-scale an already-real-micron `:x` (e.g. 0.6um * 0.2 -> a bogus
  0.12um). `1.0` is correct because `:x` needs no further scaling; the
  row-axis (`:row-idx`, a dimensionless row counter regardless of this
  choice) still genuinely needs `site-height-um`."
  1.0)

(defn stage-7-export
  "Exports the same placement three ways:
  - GDSII, via `pnr.lef-adapter/design->gdsii-structure` + `pnr.gdsii/
    export-gdsii` (binary stream, translate-only geometry -- documented
    simplification, see `pnr.lef-adapter`'s own docstring).
  - DEF, via `pnr.def-adapter/placement->def-design` (COMPONENTS section
    with real scaled microns + orientation).
  - OpenAccess, via `pnr.openaccess-adapter` (`lef-library->oa-library` +
    `placement->oa-design` + `design->flat-shapes`) -- the one export
    path that applies real per-orientation 2D transform math, closing the
    gap the GDSII path documents leaving open.

  Also builds two tiny ISOLATED single-cell placements (`:orientation-probe`)
  -- one forced to land at `:n`/R0 (identity), one forced to land at
  `:fs`/MX (mirror-about-X) -- purely so the orientation-math proof in the
  test suite can compare flattened OpenAccess geometry against an
  independently-computed expected transform without depending on shape
  ordering in the full 11-shape flattened design."
  [lef-lib {:keys [placement]}]
  (let [gdsii-structure (lef-adapter/design->gdsii-structure
                         lef-lib (:cells placement) export-x-scale-um site-height-um "TOP")
        gdsii-bytes (gdsii/export-gdsii [gdsii-structure])
        def-design (def-adapter/placement->def-design
                    "TOP" placement export-x-scale-um site-height-um die-width-um die-height-um)
        oa-library (oa-adapter/lef-library->oa-library "STDCELLS" lef-lib)
        oa-design (oa-adapter/placement->oa-design "TOP" placement oa-library)
        flat-shapes (oa-adapter/design->flat-shapes oa-library oa-design)
        probe-cell [(lef-adapter/netlist-cell-from-lef lef-lib "DFFX1" "top/probe" site-width-um)]
        probe-rows-identity [(placement/placement-row {:y 0.0 :height site-height-um
                                                         :site-width site-width-um :num-sites 12})]
        probe-rows-mirrored [(placement/placement-row {:y 0.0 :height site-height-um
                                                         :site-width site-width-um :num-sites 5})
                             (placement/placement-row {:y 1.4 :height site-height-um
                                                        :site-width site-width-um :num-sites 12})]
        placement-identity (placement/place-cells probe-cell probe-rows-identity)
        placement-mirrored (placement/place-cells probe-cell probe-rows-mirrored)
        flat-identity (oa-adapter/design->flat-shapes
                       oa-library (oa-adapter/placement->oa-design "PROBE_R0" placement-identity oa-library))
        flat-mirrored (oa-adapter/design->flat-shapes
                       oa-library (oa-adapter/placement->oa-design "PROBE_MX" placement-mirrored oa-library))]
    {:gdsii-structure gdsii-structure
     :gdsii-bytes gdsii-bytes
     :def-design def-design
     :oa-library oa-library
     :oa-design oa-design
     :flat-shapes flat-shapes
     :orientation-probe {:identity-cell (first (:cells placement-identity))
                          :mirrored-cell (first (:cells placement-mirrored))
                          :flat-identity flat-identity
                          :flat-mirrored flat-mirrored}}))

;; ---------------------------------------------------------------------------
;; Stage 8 -- UPF power intent
;; ---------------------------------------------------------------------------

(def domain-registry
  "Two power domains matching stage 5's floorplan: combinational logic
  (`PD_A`, row0) vs the registers (`PD_B`, rows 1-2) -- a real, if small,
  power-domain split (a common real pattern: shed a combinational block's
  power while its sequential state -- the registers -- must stay powered
  to retain its value)."
  [(upf-domain/create-power-domain "PD_A" ["top/pdA"])
   (upf-domain/create-power-domain "PD_B" ["top/pdB"])])

(defn build-floorplan-blocks
  "Two `pnr.floorplan` blocks whose bounds exactly cover row0 (`PD_A`) vs
  rows1-2 (`PD_B`), built via `pnr.floorplan/floorplan` + `add-block`."
  []
  (:blocks (-> (floorplan/floorplan die-width-um die-height-um)
               (floorplan/add-block {:name "block-a" :x 0.0 :y 0.0
                                      :width die-width-um :height 1.4 :power-domain "PD_A"})
               (floorplan/add-block {:name "block-b" :x 0.0 :y 1.4
                                      :width die-width-um :height 2.8 :power-domain "PD_B"}))))

(defn stage-8-power-intent
  "Validates the real placement against `domain-registry`/floorplan blocks
  via `pnr.upf-adapter/validate-domain-placement` (expect zero violations
  -- every cell's instance path is consistently scoped to the domain
  covering its physical row) and `partition-by-domain`. Also builds a
  deliberately MISASSIGNED variant (`bad-cells`: DFF0 renamed from
  `top/pdB/...` to `top/pdA/...` while staying physically in the PD_B
  block) to prove `validate-domain-placement` actually catches a real
  violation, not just passing trivially."
  [placement]
  (let [blocks (build-floorplan-blocks)
        cells (:cells placement)
        violations (upf-adapter/validate-domain-placement domain-registry cells blocks)
        partitions (upf-adapter/partition-by-domain domain-registry cells)
        bad-cells (mapv (fn [c] (if (= dff0-instance (:instance-name c))
                                  (assoc c :instance-name "top/pdA/u_dff0")
                                  c))
                        cells)
        bad-violations (upf-adapter/validate-domain-placement domain-registry bad-cells blocks)]
    {:blocks blocks :violations violations :partitions partitions
     :bad-cells bad-cells :bad-violations bad-violations}))

;; ---------------------------------------------------------------------------
;; Stage 9 -- signal integrity (IBIS-derived eye diagram)
;; ---------------------------------------------------------------------------

(def demo-ibis-model
  "A simplified 1.8V I/O buffer IBIS model: pulldown/pullup V-I tables
  spanning 0 -> 1.8V (a real, if minimal, output swing), and a ramp of
  0.9V over 300ps into a 50-ohm load."
  (-> (ibis/model {:name "DEMO_IO_1V8" :model-type :io
                    :ramp {:dv 0.9 :dt 300.0e-12 :r-load 50.0}})
      (ibis/add-point :pulldown 0.0 0.0)
      (ibis/add-point :pulldown 1.8 0.05)
      (ibis/add-point :pullup 0.0 -0.05)
      (ibis/add-point :pullup 1.8 0.0)))

(def si-overrides
  "Link-level parameters `signal-integrity.ibis-adapter/eye-data-from-ibis`
  cannot derive from an IBIS `[Model]` section alone (see that ns's
  docstring): a 2Gbps link, 20mV RMS noise, 5ps RMS jitter, 200 bits."
  {:bit-rate-gbps 2.0 :noise-rms-mv 20.0 :jitter-rms-ps 5.0 :num-bits 200})

(defn stage-9-signal-integrity
  "Derives amplitude/rise-time from `demo-ibis-model`'s real V-I/ramp data
  and generates eye-diagram data via
  `signal-integrity.ibis-adapter/eye-data-from-ibis`."
  []
  {:model demo-ibis-model
   :amplitude-mv (si-adapter/model->amplitude-mv demo-ibis-model)
   :rise-time-ps (si-adapter/model->rise-time-ps demo-ibis-model)
   :eye-data (si-adapter/eye-data-from-ibis demo-ibis-model si-overrides)})

;; ---------------------------------------------------------------------------
;; Stage 10 -- UVM-style driver/monitor verification against rtl.simulator
;; ---------------------------------------------------------------------------

(def verification-stimulus
  "A small stimulus sequence against `q0` -- one of this circuit's own net
  names (the same `q0` that stage 2's netlist and stage 3's timing job
  operate on)."
  [{:time 0 :value [:zero]}
   {:time 5 :value [:one]}
   {:time 10 :value [:zero]}
   {:time 15 :value [:one]}])

(defn stage-10-verification
  "Drives + monitors `q0` on a fresh `rtl.simulator` via
  `org-accellera-uvm.rtl-driver/run-simple-testbench`. `driven-signal` and
  `watched-signal` are deliberately the SAME net (`q0`): `rtl.simulator`
  has no gate-level evaluator of its own (it only replays scheduled value
  changes -- see that namespace's docstring), so there is no automatic
  NOT/XOR/DFF response to observe on a DIFFERENT watched signal without
  fabricating one. Driving and watching the same real net still
  genuinely exercises the driver -> simulator -> monitor round-trip
  (`uvm.rtl-driver`'s actual job), and lets the test assert the classic
  UVM invariant: what the monitor observed IS what the driver applied."
  []
  (uvm-driver/run-simple-testbench (rtl-sim/simulator) "q0" "q0" verification-stimulus 5))

;; ---------------------------------------------------------------------------
;; Full flow
;; ---------------------------------------------------------------------------

(defn run-full-flow
  "Threads the whole pipeline on the 2-bit counter and returns every
  stage's result keyed by stage name, so a caller can inspect the full
  trace end to end."
  []
  (let [synth-result (stage-2-synthesize)
        netlist (:netlist synth-result)
        lib-result (stage-4-cell-library)
        lef-lib (:lib lib-result)
        placement-result (stage-5-placement lef-lib)]
    {:stage-1-rtl-parse {:verilog (stage-1-parse-verilog)
                          :vhdl (stage-1-parse-vhdl)}
     :stage-2-synthesis synth-result
     :stage-3-timing-signoff (stage-3-timing-signoff netlist sdc-script)
     :stage-4-cell-library lib-result
     :stage-5-placement placement-result
     :stage-6-routing (stage-6-routing lef-lib placement-result)
     :stage-7-export (stage-7-export lef-lib placement-result)
     :stage-8-power-intent (stage-8-power-intent (:placement placement-result))
     :stage-9-signal-integrity (stage-9-signal-integrity)
     :stage-10-verification (stage-10-verification)}))
