(ns kotoba-eda-app
  "Reagent port of the kotoba EDA Flow Workbench's interactive logic
  (formerly resources/eda_app.js, ~900 lines of vanilla JS DOM patching).
  Compiled by `npx shadow-cljs release app` (see shadow-cljs.edn) to
  resources/main.js. Plain `cljs.main` was tried first (no shadow-cljs/npm,
  matching kotoba-lang's usual convention) but its automatic npm/React
  module resolution never linked up cleanly even with node_modules present;
  shadow-cljs owns that wiring correctly, so this one directory takes on
  npm/shadow-cljs as its build dependency rather than fighting that (see
  deps.edn's comment). kotoba_eda_build.clj then embeds resources/main.js
  into docs/eda/index.html exactly where resources/eda_app.js used to go.

  CLJS-only (not .cljc): every responsibility here — File API reads, a 2D
  canvas context, Blob/URL downloads — is browser-only, same as the
  original. `kotoba_eda_ui.cljc`'s static SSR shell (nav, initial-state
  markup) is unchanged; on load this namespace's `init!` replaces the
  content of `#app` (see kotoba_eda_ui.cljc `body`) with a fully reactive
  render bound to a single ratom, restoring `id=\"eda-canvas\"` +
  `data-kami-engine=\"render-ir\"` on the canvas it (re)creates so the
  kami-engine contract survives the remount.

  Known, deliberate output-shape differences from the original JS (noted
  here rather than silently): state/EDN keys are kebab-case
  (`:output-cid`, not `outputCid`) per CLJS convention, and the two
  \"download EDN\" buttons now emit `pr-str` output instead of the
  original's hand-rolled toEdn — both are valid EDN, formatting just
  differs. JSON downloads (datoms/packet/signoff-evidence-template) use
  `clj->js` + `JSON.stringify` and preserve the original's `namespace/name`
  key shape via a custom :keyword-fn so those payloads stay
  structurally identical to before."
  (:require [reagent.core :as r]
            [reagent.dom :as rdom]
            [clojure.string :as str]))

;; -- static reference data (kept as vectors of tuples, same shape as the
;;    original JS arrays, since the render fns below destructure them
;;    positionally) --------------------------------------------------------

(def stages
  [["spec" "Spec" "requirements, IO, clocks, power, test intent"]
   ["arch" "Architecture" "IP blocks, buses, memories, analog boundaries"]
   ["source" "Source" ".kotoba, .cljc, RTL, SPICE, constraints"]
   ["sim" "Simulation" "unit, mixed-signal, waveform, formal checks"]
   ["synth" "Synthesis" "netlist, timing constraints, area and power"]
   ["pnr" "Floorplan/P&R" "placement, routing, congestion, clocks"]
   ["signoff" "Signoff" "DRC, LVS, STA, IR, EM, SPICE reports"]
   ["tapeout" "Tapeout" "GDS/OASIS, LEF/DEF, netlist and waiver bundle"]
   ["mask" "Mask order" "reticle plan, mask shop package, release gate"]
   ["wafer" "Wafer lot" "process traveller, PCM, lot sampling"]
   ["probe" "Probe" "wafer sort, binning, known-good die data"]
   ["package" "Package" "assembly, substrate, wirebond/flip-chip, thermal"]
   ["final" "Final test" "ATE vectors, QA, yield ramp, ship release"]])

(def gates
  [["pdk-license" "PDK license" "PDK と rule deck の利用権"]
   ["nda-export" "NDA / export" "外部推論と foundry 送信の可否"]
   ["mask-budget" "Mask budget" "有償 mask order の承認"]
   ["foundry-slot" "Foundry slot" "lot 予約と upload window"]
   ["human-signoff" "Human signoff" "LLM ではない責任者承認"]])

(def format-registry
  [["rtl/systemverilog" [".sv" ".svh"] "source" ["design/source-frozen" "simulation/rtl"]]
   ["rtl/verilog" [".v"] "source" ["design/source-frozen" "simulation/rtl"]]
   ["rtl/vhdl" [".vhd" ".vhdl"] "source" ["design/source-frozen" "simulation/rtl"]]
   ["analog/spice" [".sp" ".spi" ".cir" ".ckt"] "netlist" ["design/source-frozen" "simulation/mixed-signal"]]
   ["analog/cdl" [".cdl"] "netlist" ["simulation/mixed-signal" "signoff/drc-lvs-sta"]]
   ["constraint/sdc" [".sdc"] "constraint" ["design/spec-reviewed" "implementation/synthesis"]]
   ["constraint/upf" [".upf"] "constraint" ["design/spec-reviewed"]]
   ["library/liberty" [".lib"] "library" ["implementation/synthesis" "signoff/drc-lvs-sta"]]
   ["physical/lef" [".lef"] "physical" ["implementation/pnr"]]
   ["physical/def" [".def"] "physical" ["implementation/pnr"]]
   ["layout/gdsii" [".gds" ".gdsii"] "layout" ["release/tapeout-bundle" "manufacturing/mask-gated"]]
   ["layout/oasis" [".oas" ".oasis"] "layout" ["release/tapeout-bundle" "manufacturing/mask-gated"]]
   ["wave/vcd" [".vcd"] "waveform" ["simulation/rtl"]]
   ["wave/fst" [".fst"] "waveform" ["simulation/rtl"]]
   ["timing/sdf" [".sdf"] "timing" ["signoff/drc-lvs-sta"]]
   ["power/saif" [".saif"] "power" ["signoff/drc-lvs-sta"]]
   ["test/stil" [".stil"] "test" ["manufacturing/probe-package-ate"]]
   ["test/wgl" [".wgl"] "test" ["manufacturing/probe-package-ate"]]
   ["report/generic" [".rpt" ".log" ".drc" ".lvs"] "report" ["signoff/drc-lvs-sta"]]
   ["pdk/rule-deck" [".rule" ".rules" ".deck"] "pdk" ["signoff/drc-lvs-sta"]]])

(def runner-adapters
  [{:id "runner/verilator-lint" :name "Verilator lint" :software "sw/verilator"
    :formats ["rtl/verilog" "rtl/systemverilog"] :operation "op/lint"
    :command ["verilator" "--lint-only" "--Wall" "$inputs"]}
   {:id "runner/verilator-vcd" :name "Verilator simulation scaffold" :software "sw/verilator"
    :formats ["rtl/verilog" "rtl/systemverilog"] :operation "op/simulate"
    :command ["verilator" "--cc" "--trace" "$inputs"]}
   {:id "runner/yosys-synth" :name "Yosys synthesis" :software "sw/yosys"
    :formats ["rtl/verilog" "rtl/systemverilog"] :operation "op/synthesize"
    :command ["yosys" "-p" "read_verilog -sv $inputs; synth; stat; write_json out/netlist.json"]}
   {:id "runner/opensta-timing" :name "OpenSTA timing" :software "sw/opensta"
    :formats ["constraint/sdc" "library/liberty" "timing/sdf"] :operation "op/analyze-timing"
    :command ["sta" "-exit" "flow.tcl"]}
   {:id "runner/openroad-pnr" :name "OpenROAD place and route" :software "sw/openroad"
    :formats ["physical/lef" "physical/def" "constraint/sdc" "library/liberty"] :operation "op/route"
    :command ["openroad" "flow.tcl"]}
   {:id "runner/klayout-drc" :name "KLayout DRC/layout summary" :software "sw/klayout"
    :formats ["layout/gdsii" "layout/oasis" "pdk/rule-deck"] :operation "op/drc"
    :command ["klayout" "-b" "-r" "$rule_deck" "$layout"]}
   {:id "runner/netgen-lvs" :name "Netgen LVS" :software "sw/netgen"
    :formats ["analog/spice" "analog/cdl" "layout/gdsii"] :operation "op/lvs"
    :command ["netgen" "-batch" "lvs" "$layout_netlist" "$source_netlist" "setup.tcl"]}
   {:id "runner/ngspice" :name "ngspice simulation" :software "sw/ngspice"
    :formats ["analog/spice"] :operation "op/simulate"
    :command ["ngspice" "-b" "$inputs" "-o" "out/ngspice.log"]}])

(def signoff-requirements
  [{:type "signoff/timing-pvt" :coverage "coverage/timing-corners" :tool "sw/opensta" :operation "op/analyze-timing" :label "OpenSTA PVT timing" :min-corners 3}
   {:type "signoff/route" :coverage "coverage/power-activity" :tool "sw/openroad" :operation "op/route" :label "OpenROAD route" :max-overflow 0}
   {:type "signoff/drc" :coverage "coverage/drc-lvs" :tool "sw/klayout" :operation "op/drc" :label "KLayout DRC" :max-violations 0}
   {:type "signoff/lvs" :coverage "coverage/drc-lvs" :tool "sw/netgen" :operation "op/lvs" :label "Netgen LVS" :max-mismatches 0}
   {:type "signoff/spice-corner" :coverage "coverage/mixed-signal" :tool "sw/ngspice" :operation "op/simulate" :label "ngspice corners"}
   {:type "signoff/ate-pattern" :coverage "coverage/ate-pattern" :tool "sw/ate-adapter" :operation "op/ate" :label "ATE pattern" :min-coverage 95}])

;; -- state -----------------------------------------------------------------

(defonce state
  (r/atom
   {:stage 0
    :view "layout"
    :issue nil
    :approvals #{"pdk-license"}
    :datoms []
    :llm []
    :co nil
    :maturity nil
    :artifacts []
    :runner-plan nil
    :murakumo-payload nil
    :runner-results []
    :signoff-evidence []
    :render-ir nil
    ;; form fields — DOM-read via cfg() in the original, now just state
    :target "sensor-asic"
    :process "sky130"
    :die 16
    :volume 25
    :ip #{"cpu" "sram" "otp"}}))

(defn cfg [s]
  {:target (:target s) :process (:process s) :die (:die s) :volume (:volume s)
   :ip (filterv (:ip s) ["cpu" "sram" "analog" "serdes" "ml" "otp"])})

;; -- pure helpers ------------------------------------------------------------

(defn edn-hash [s]
  (let [h (reduce (fn [h i] (js/Math.imul (bit-xor h (.charCodeAt s i)) 16777619))
                   2166136261
                   (range (count s)))]
    (str "bafyeda" (.padStart (.toString (unsigned-bit-shift-right h 0) 36) 7 "0"))))

(defn kw->str [k]
  (if-let [ns (namespace k)] (str ns "/" (name k)) (name k)))

(defn ->json
  ([x] (.stringify js/JSON (clj->js x :keyword-fn kw->str)))
  ([x indent] (.stringify js/JSON (clj->js x :keyword-fn kw->str) nil indent)))

(defn download-text! [filename text mime]
  (let [blob (js/Blob. #js [text] #js {:type mime})
        a (.createElement js/document "a")]
    (set! (.-href a) (.createObjectURL js/URL blob))
    (set! (.-download a) filename)
    (.click a)
    (.revokeObjectURL js/URL (.-href a))))

(defn extension [path]
  (let [i (.lastIndexOf path ".")]
    (if (>= i 0) (str/lower-case (.slice path i)) "")))

(defn format-for-file [name]
  (let [ext (extension name)
        hit (first (filter (fn [[_ exts _ _]] (some #{ext} exts)) format-registry))]
    (if hit
      (let [[id _ kind evidence] hit] {:id id :kind kind :evidence evidence :ext ext})
      {:id "unknown" :kind "unknown" :evidence [] :ext ext})))

(defn count-matches [text re]
  (count (or (.match text re) #js [])))

(defn parse-artifact [name text bytes]
  (let [fmt (format-for-file name)
        fmt-id (:id fmt)
        lower (str/lower-case text)
        base {:format fmt-id :kind (:kind fmt) :bytes bytes}
        [summary findings]
        (cond
          (str/starts-with? fmt-id "rtl/")
          (let [modules (count-matches text (js/RegExp. "\\bmodule\\b" "g"))
                always-blocks (count-matches text (js/RegExp. "\\balways(_ff|_comb|_latch)?\\b" "g"))
                assigns (count-matches text (js/RegExp. "\\bassign\\b" "g"))]
            [(assoc base :modules modules :always-blocks always-blocks :assigns assigns)
             (if (zero? modules) [["high" "RTL source has no module declaration."]] [])])

          (= fmt-id "constraint/sdc")
          (let [clocks (count-matches text (js/RegExp. "\\bcreate_clock\\b" "g"))
                false-paths (count-matches text (js/RegExp. "\\bset_false_path\\b" "g"))]
            [(assoc base :clocks clocks :false-paths false-paths)
             (if (zero? clocks) [["medium" "SDC has no create_clock constraint."]] [])])

          (str/starts-with? fmt-id "analog/")
          (let [subckts (count-matches text (js/RegExp. "^\\.subckt\\b" "gim"))
                devices (count-matches text (js/RegExp. "^[xmrcdlq]\\w*" "gim"))]
            [(assoc base :subckts subckts :devices devices)
             (if (zero? subckts) [["medium" "Netlist has no .subckt boundary."]] [])])

          (= fmt-id "library/liberty")
          [(assoc base
                  :cells (count-matches text (js/RegExp. "\\bcell\\s*\\(" "g"))
                  :pins (count-matches text (js/RegExp. "\\bpin\\s*\\(" "g")))
           []]

          (= fmt-id "physical/def")
          [(assoc base
                  :components (count-matches text (js/RegExp. "\\bCOMPONENTS\\b" "g"))
                  :nets (count-matches text (js/RegExp. "\\bNETS\\b" "g")))
           []]

          (= fmt-id "wave/vcd")
          [(assoc base
                  :signals (count-matches text (js/RegExp. "\\$var\\b" "g"))
                  :timestamps (count-matches text (js/RegExp. "^#\\d+" "gm")))
           []]

          (= (:kind fmt) "report")
          (let [errors (count-matches lower (js/RegExp. "\\berror\\b" "g"))
                warnings (count-matches lower (js/RegExp. "\\bwarning\\b" "g"))
                violations (count-matches lower (js/RegExp. "\\b(violation|violated|drc|lvs|slack)\\b" "g"))]
            [(assoc base :errors errors :warnings warnings :violations violations)
             (if (or (pos? errors) (pos? violations))
               [["high" (str (+ errors violations) " report risk markers found.")]]
               [])])

          (= (:kind fmt) "layout")
          [(assoc base :binary-layout true
                  :note "Binary layout accepted as CID evidence; deep GDS/OASIS parse requires server adapter.")
           []]

          :else [base []])]
    (merge fmt {:summary summary :findings findings})))

(defn evidence-for [s check-id]
  (some (fn [a] (some #{check-id} (:evidence a))) (:artifacts s)))

(defn score [c s]
  (let [complexity (+ (/ (:die c) 144) (* (count (:ip c)) 0.055)
                       (if (= (:process c) "cmos28") 0.18 0)
                       (if (= (:process c) "bcd180") 0.1 0))
        issue-penalty (if (:issue s) 0.08 0)
        signoff (max 0 (min 1 (- (/ (:stage s) (dec (count stages))) issue-penalty)))
        yield-pct (max 42 (min 98 (+ (- 96 (* complexity 18) (* issue-penalty 100)) (* signoff 4))))
        cost (js/Math.round (* (+ (* (:die c) 2.8) (* (:volume c) 0.18) (* (count (:ip c)) 8))
                                (cond (= (:process c) "cmos28") 4.5
                                      (= (:process c) "bcd180") 2.2
                                      :else 1)))]
    {:complexity complexity :signoff signoff :yield-pct yield-pct :cost cost}))

(defn co-sientist-review [s]
  (let [c (cfg s)
        sc (score c s)
        gate-coverage (/ (count (:approvals s)) (count gates))
        quality (max 0 (min 100 (js/Math.round (+ (* (:signoff sc) 55) (* gate-coverage 25)
                                                    (if (:issue s) -18 10)
                                                    (if (>= (:die c) 100) -4 6)))))
        uiux (max 0 (min 100 (js/Math.round (+ 72 (* gate-coverage 8)
                                                (if (:issue s) -10 4)
                                                (if (>= (:signoff sc) 0.5) 6 0)))))
        findings (cond-> []
                   (< quality 70) (conj ["high" "Add missing evidence CIDs before release or foundry handoff."])
                   (:issue s) (conj ["high" "Resolve timing/DRC correlation before tapeout."])
                   (< gate-coverage 0.8) (conj ["medium" "Approve remaining policy gates or keep vendor actions disabled."])
                   (< uiux 82) (conj ["medium" "Promote next action, blocking gate and artifact status in the primary scan path."]))
        findings (if (seq findings) findings
                   [["info" "Quality and UIUX review is clean enough to continue to the next EDA stage."]])]
    {:quality quality :uiux uiux :gate-coverage gate-coverage :findings findings}))

(def readiness-checks
  [["design/spec-reviewed" "design" 1 "requirements, interfaces and power/timing intent reviewed"]
   ["design/source-frozen" "design" 2 ".kotoba/.cljc/RTL/SPICE sources have CIDs"]
   ["simulation/rtl" "simulation" 3 "RTL/unit regression and waveform summary available"]
   ["simulation/mixed-signal" "simulation" 3 "SPICE or mixed-signal corner smoke tests available"]
   ["implementation/synthesis" "implementation" 4 "synthesis reports, netlist and constraints are reproducible"]
   ["implementation/pnr" "implementation" 5 "DEF, congestion, clock and route reports are reproducible"]
   ["signoff/drc-lvs-sta" "signoff" 6 "DRC/LVS/STA evidence CIDs are present and current"]
   ["release/tapeout-bundle" "release" 7 "GDS/OASIS, waiver manifest and release packet exist"]
   ["manufacturing/mask-gated" "manufacturing" 8 "mask order is explicit, budgeted and human-approved"]
   ["manufacturing/probe-package-ate" "manufacturing" 12 "probe, package and final ATE plans are traceable"]])

(defn simulation-matrix [s]
  (let [c (cfg s)
        sc (score c s)
        sim-reached (>= (:stage s) 3)
        signoff-reached (>= (:stage s) 6)]
    [["RTL unit regression" "Verilator" (if sim-reached "pass" "pending")
      (if sim-reached (min 98 (js/Math.round (+ 72 (* (:signoff sc) 20)))) 0)]
     ["Formal smoke" "Yosys" (if sim-reached "pass" "pending") (if sim-reached 68 0)]
     ["Mixed-signal corners" "ngspice"
      (if (some #{"analog"} (:ip c)) (if sim-reached "pass" "pending") "not-applicable")
      (if (some #{"analog"} (:ip c)) (if sim-reached 61 0) 100)]
     ["Timing corners" "OpenSTA" (if signoff-reached "pass" "pending") (if signoff-reached 84 0)]
     ["Power activity" "OpenSTA + SAIF" (if signoff-reached "pass" "pending") (if signoff-reached 76 0)]]))

(defn result-for [s tool operation]
  (first (filter #(and (= (:tool %) tool) (= (:operation %) operation)) (:runner-results s))))

(defn normalize-evidence [row]
  (let [g (fn [& ks] (some #(get row %) ks))
        metrics (or (:metrics row) {})
        typ (g :type :evidence-type)
        evidence {:type typ
                  :tool (g :tool)
                  :operation (g :operation)
                  :status (or (g :status) "passed")
                  :coverage (js/Number (or (g :coverage) 0))
                  :corners (js/Number (or (g :corners) (:corners metrics) (if (:corner row) 1 0)))
                  :corner (or (g :corner) "")
                  :pvt (or (g :pvt) "")
                  :slack-ns (js/Number (or (g :slack-ns) (:slack-ns metrics) -9999))
                  :overflow (js/Number (or (g :overflow) (:overflow metrics) 0))
                  :violations (js/Number (or (g :violations) (:violations metrics) 0))
                  :mismatches (js/Number (or (g :mismatches) (:mismatches metrics) 0))
                  :vector-coverage (js/Number (or (g :vector-coverage) (g :coverage) 0))
                  :output-cid (or (g :output-cid :evidence-cid) (edn-hash (->json row)))
                  :waiver-cid (or (g :waiver-cid) "")}]
    (if (:type evidence)
      evidence
      (assoc evidence :type
             (or (:type (first (filter #(and (= (:tool %) (:tool evidence))
                                              (= (:operation %) (:operation evidence)))
                                        signoff-requirements)))
                 "signoff/unknown")))))

(defn signoff-evidence-for [s typ]
  (first (filter #(= (:type %) typ) (:signoff-evidence s))))

(defn signoff-evidence-assessment [s]
  (let [rows (mapv
              (fn [req]
                (let [e (signoff-evidence-for s (:type req))
                      pass? (boolean
                             (and e
                                  (case (:type req)
                                    "signoff/timing-pvt" (and (= (:status e) "passed")
                                                               (>= (:corners e) (:min-corners req))
                                                               (>= (:slack-ns e) 0))
                                    "signoff/route" (and (= (:status e) "passed")
                                                          (<= (:overflow e) (:max-overflow req)))
                                    "signoff/drc" (and (= (:status e) "passed")
                                                        (<= (:violations e) (:max-violations req)))
                                    "signoff/lvs" (and (= (:status e) "passed")
                                                        (<= (:mismatches e) (:max-mismatches req)))
                                    "signoff/ate-pattern" (and (= (:status e) "passed")
                                                                (>= (:vector-coverage e) (:min-coverage req)))
                                    (= (:status e) "passed"))))]
                  (assoc req
                         :status (if pass? "passed" "blocked")
                         :source (if e "signoff-evidence" "missing")
                         :score (if pass? (max (or (:coverage e) 0) (or (:min-coverage req) 95))
                                  (or (:coverage e) 0))
                         :evidence (or (:output-cid e) "")
                         :blocker (if pass? "" (if e "metric-threshold-not-met" "evidence-missing")))))
              signoff-requirements)
        passed (count (filter #(= (:status %) "passed") rows))]
    {:source (if (seq (:signoff-evidence s)) "signoff-evidence" "missing")
     :rows rows :passed passed :total (count rows)
     :score (js/Math.round (/ (reduce + (map :score rows)) (count rows)))}))

(defn signoff-coverage-for [s id]
  (let [rows (filter #(= (:coverage %) id) (:rows (signoff-evidence-assessment s)))]
    (when (seq rows)
      {:source "signoff-evidence"
       :status (if (every? #(= (:status %) "passed") rows) "pass" "blocked")
       :score (js/Math.round (/ (reduce + (map :score rows)) (count rows)))
       :evidence (str/join "," (filter seq (map :evidence rows)))})))

(defn coverage-assessment [s]
  (let [base (simulation-matrix s)
        source (cond (seq (:signoff-evidence s)) "signoff-evidence"
                      (seq (:runner-results s)) "runner-result"
                      :else "stage-model")
        specs [["coverage/rtl-unit" "Verilator" "sw/verilator" "op/simulate" (nth base 0)]
               ["coverage/formal-smoke" "Yosys" "sw/yosys" "op/synthesize" (nth base 1)]
               ["coverage/mixed-signal" "ngspice" "sw/ngspice" "op/simulate" (nth base 2)]
               ["coverage/timing-corners" "OpenSTA" "sw/opensta" "op/analyze-timing" (nth base 3)]
               ["coverage/power-activity" "OpenSTA" "sw/opensta" "op/analyze-power" (nth base 4)]
               ["coverage/drc-lvs" "KLayout/Netgen" "sw/klayout" "op/drc"
                ["DRC/LVS" "KLayout/Netgen" "pending" (if (>= (:stage s) 6) 40 0)]]
               ["coverage/ate-pattern" "ATE" "sw/ate-adapter" "op/ate"
                ["ATE pattern" "ATE" "pending" (if (>= (:stage s) 12) 35 0)]]]
        rows (mapv (fn [[id label tool op fallback]]
                     (let [rr (result-for s tool op)
                           sr (signoff-coverage-for s id)
                           [_ _ fb-status fb-score] fallback]
                       {:id id :label label
                        :source (cond sr (:source sr) rr "runner-result" :else source)
                        :status (or (:status sr) (:status rr) fb-status)
                        :score (or (:score sr) (:coverage rr) fb-score)
                        :evidence (or (:evidence sr) (:output-cid rr) (:adapter rr) "")}))
                   specs)]
    {:source source :rows rows :score (js/Math.round (/ (reduce + (map :score rows)) (count rows)))}))

(defn maturity-assessment [s]
  (let [signoff (signoff-evidence-assessment s)
        checks (mapv
                (fn [[id category required-stage role]]
                  (let [stage-ok (>= (:stage s) required-stage)
                        artifact-ok (boolean (evidence-for s id))
                        signoff-ok (cond
                                     (= id "signoff/drc-lvs-sta")
                                     (every? (fn [typ] (some #(and (= (:type %) typ) (= (:status %) "passed")) (:rows signoff)))
                                             ["signoff/timing-pvt" "signoff/drc" "signoff/lvs"])
                                     (= id "manufacturing/probe-package-ate")
                                     (boolean (some #(and (= (:type %) "signoff/ate-pattern") (= (:status %) "passed")) (:rows signoff)))
                                     :else false)
                        gate-ok (if (= id "manufacturing/mask-gated")
                                  (and (contains? (:approvals s) "mask-budget") (contains? (:approvals s) "human-signoff"))
                                  true)
                        pass? (and (or stage-ok artifact-ok signoff-ok) gate-ok (not (:issue s)))]
                    {:id id :category category :role role
                     :status (if pass? "pass" "block")
                     :blocker (cond (:issue s) "blocked-by-signoff-issue"
                                     (not (or stage-ok artifact-ok signoff-ok)) "stage-or-evidence-missing"
                                     (not gate-ok) "policy-gate-missing"
                                     :else "")
                     :cid (if pass?
                            (or (:cid (first (filter #(some #{id} (:evidence %)) (:artifacts s))))
                                (:evidence (first (filter :evidence (:rows signoff))))
                                (edn-hash (str "readiness" id (->json (cfg s)))))
                            "")}))
                readiness-checks)
        passed (count (filter #(= (:status %) "pass") checks))
        readiness (js/Math.round (* (/ passed (count checks)) 100))
        sims (simulation-matrix s)
        coverage (coverage-assessment s)
        sim-coverage (:score coverage)
        level (cond
                (and (= passed (count checks)) (>= sim-coverage 85) (= (:passed signoff) (:total signoff))
                     (contains? (:approvals s) "foundry-slot") (contains? (:approvals s) "human-signoff"))
                "MRL release-ready"
                (and (>= readiness 80) (>= sim-coverage 75)) "MRL pilot-ready"
                (and (>= readiness 55) (>= sim-coverage 50)) "MRL engineering-ready"
                (>= readiness 30) "MRL prototype"
                :else "MRL concept")
        useable-for (case level
                      "MRL release-ready" ["foundry handoff" "mask order" "pilot lot" "ATE release"]
                      "MRL pilot-ready" ["internal tapeout review" "MPW precheck" "package planning"]
                      "MRL engineering-ready" ["design review" "simulation regression" "P&R iteration"]
                      "MRL prototype" ["architecture review" "source bringup" "testbench work"]
                      ["requirements work"])]
    {:level level :readiness readiness :sim-coverage sim-coverage :passed passed :total (count checks)
     :checks checks :sims sims :coverage coverage :signoff signoff :useable-for useable-for}))

;; -- state-mutating actions --------------------------------------------------

(defn transact! [kind body]
  (swap! state update :datoms
         (fn [ds] (cons (merge {:time (.toISOString (js/Date.)) :kind kind
                                 :stage (first (nth stages (:stage @state)))}
                                body)
                        ds))))

(defn proposal!
  ([text] (proposal! text "info"))
  ([text severity]
   (swap! state update :llm
          (fn [ls] (cons {:time (.toISOString (js/Date.)) :severity severity :text text} ls)))))

(defn ingest-one-artifact! [file]
  (let [fmt (format-for-file (.-name file))
        finish (fn [text]
                 (let [cid (edn-hash (str (.-name file) ":" (.-size file) ":" (.slice text 0 4096)))
                       parsed (parse-artifact (.-name file) text (.-size file))
                       artifact {:name (.-name file) :cid cid :format (:id parsed) :kind (:kind parsed)
                                  :evidence (:evidence parsed) :summary (:summary parsed) :findings (:findings parsed)}]
                   (swap! state update :artifacts #(cons artifact %))
                   (transact! "eda.artifact/ingest" {:path (:name artifact) :cid cid :format (:format artifact)
                                                       :bytes (.-size file) :evidence (:evidence artifact)})
                   (transact! "eda.parser/summary" {:cid cid :format (:format artifact) :summary (:summary artifact)})
                   (doseq [[severity text] (:findings artifact)]
                     (transact! "eda.report/finding" {:cid cid :severity severity :text text}))))]
    (if (or (= (:kind fmt) "layout") (= (:id fmt) "wave/fst"))
      (js/Promise.resolve (finish ""))
      (.then (.text file) finish))))

(defn ingest-artifacts! [files]
  (-> (reduce (fn [p f] (.then p (fn [_] (ingest-one-artifact! f)))) (js/Promise.resolve nil) files)
      (.then (fn [_]
               (proposal! (str (count files) " artifact(s) ingested and converted to EDN manifest summaries in-browser. External EDA execution still requires a runner adapter.") "info")))))

(defn import-runner-results! [files]
  (-> (reduce
       (fn [p file]
         (.then p (fn [_]
                    (.then (.text file)
                           (fn [text]
                             (let [parsed (js->clj (.parse js/JSON text) :keywordize-keys true)
                                   rows (cond (vector? parsed) parsed
                                              (sequential? parsed) (vec parsed)
                                              (:results parsed) (:results parsed)
                                              :else [parsed])]
                               (doseq [row rows]
                                 (let [result {:adapter (:adapter row) :tool (:tool row) :operation (:operation row)
                                                :status (or (:status row) "passed")
                                                :coverage (js/Number (or (:coverage row) (if (= (:status row) "failed") 20 80)))
                                                :output-cid (or (:output-cid row) (edn-hash (->json row)))}]
                                   (swap! state update :runner-results #(cons result %))
                                   (transact! "eda.run/result" result)
                                   (transact! "eda.coverage/sample" {:tool (:tool result) :operation (:operation result)
                                                                       :status (:status result) :coverage (:coverage result)
                                                                       :evidence-cid (:output-cid result)}))))))))
       (js/Promise.resolve nil) files)
      (.then (fn [_] (proposal! (str (count files) " runner result file(s) imported; coverage now prefers runner-result evidence over stage fallback.") "info"))))))

(defn import-signoff-evidence! [files]
  (-> (reduce
       (fn [p file]
         (.then p (fn [_]
                    (.then (.text file)
                           (fn [text]
                             (let [parsed (js->clj (.parse js/JSON text) :keywordize-keys true)
                                   rows (cond (vector? parsed) parsed
                                              (sequential? parsed) (vec parsed)
                                              (:results parsed) (:results parsed)
                                              (:evidence parsed) (:evidence parsed)
                                              :else [parsed])]
                               (doseq [row rows]
                                 (let [evidence (normalize-evidence row)]
                                   (swap! state update :signoff-evidence #(cons evidence %))
                                   (swap! state update :runner-results
                                          #(cons {:adapter (:type evidence) :tool (:tool evidence) :operation (:operation evidence)
                                                   :status (:status evidence) :coverage (:coverage evidence)
                                                   :output-cid (:output-cid evidence)}
                                                  %))
                                   (transact! "eda.signoff/evidence" evidence)
                                   (transact! "eda.coverage/sample" {:tool (:tool evidence) :operation (:operation evidence)
                                                                       :status (:status evidence) :coverage (:coverage evidence)
                                                                       :evidence-cid (:output-cid evidence)}))))))))
       (js/Promise.resolve nil) files)
      (.then (fn [_] (proposal! (str (count files) " signoff evidence file(s) imported; release readiness now requires PVT/DRC/LVS/ATE evidence thresholds.") "info"))))))

(defn build-preview-runner-plan [s]
  {:eda.job/id "preview"
   :eda.job/adapters
   (mapv (fn [adapter]
           (let [inputs (filter #(some #{(:format %)} (:formats adapter)) (:artifacts s))]
             {:eda.job.adapter/id (:id adapter) :eda.job.adapter/name (:name adapter)
              :eda.job.adapter/software (:software adapter)
              :eda.job.adapter/status (if (seq inputs) "ready" "missing-inputs")}))
         runner-adapters)})

(defn build-runner-plan! []
  (let [s @state
        job {:eda.job/schema 1 :eda.job/kind "eda.runner/job-plan"
             :eda.job/id (str "eda-job-" (.slice (edn-hash (->json (:artifacts s))) -8))
             :eda.job/mode "dry-run-until-host-approved"
             :eda.job/adapters
             (mapv (fn [adapter]
                     (let [inputs (filter #(some #{(:format %)} (:formats adapter)) (:artifacts s))]
                       {:eda.job.adapter/id (:id adapter) :eda.job.adapter/name (:name adapter)
                        :eda.job.adapter/software (:software adapter) :eda.job.adapter/operation (:operation adapter)
                        :eda.job.adapter/status (if (seq inputs) "ready" "missing-inputs")
                        :eda.job.adapter/inputs (mapv (fn [a] {:path (:name a) :cid (:cid a) :format (:format a)}) inputs)
                        :eda.job.adapter/command
                        {:eda.command/argv (:command adapter)
                         :eda.command/input-cids (mapv :cid inputs)
                         :eda.command/input-paths (mapv :name inputs)
                         :eda.command/policy {:network "deny" :filesystem "workspace-only" :approval "required-before-exec"}}}))
                   runner-adapters)}]
    (swap! state assoc :runner-plan job)
    (transact! "eda.runner/plan" {:id (:eda.job/id job)
                                   :ready (count (filter #(= (:eda.job.adapter/status %) "ready") (:eda.job/adapters job)))
                                   :total (count (:eda.job/adapters job))})
    (proposal! "Runner adapter plan built. Download it and execute with host/murakumo runner after policy approval." "info")
    job))

(defn build-murakumo-payload! []
  (let [s @state
        runner-plan (or (:runner-plan s) (build-preview-runner-plan s))
        run-id (str "eda-run-" (.slice (edn-hash (->json {:runner-plan runner-plan :artifacts (:artifacts s) :gates (vec (:approvals s))})) -8))
        payload {:eda.murakumo/schema 1 :eda.murakumo/run-id run-id :eda.murakumo/kind "eda.runner/job"
                 :eda.murakumo/project (str "kotoba-eda-" (:target (cfg s))) :eda.murakumo/mode "dry-run"
                 :eda.murakumo/placement {:reach ["tailnet" "local-workspace"]
                                           :class ["mac-mini" "linux-workstation" "licensed-runner"]
                                           :requires ["cpu" "workspace-fs"] :forbids ["public-internet-egress"]}
                 :eda.murakumo/policy {:network "deny-by-default" :filesystem "workspace-only" :license-check "required"
                                        :pdk-export "deny-by-default" :paid-action "approval-required"
                                        :human-signoff "required-for-vendor-upload"
                                        :approvals (into {} (map (fn [[id]] [id (contains? (:approvals s) id)]) gates))}
                 :eda.murakumo/runner-plan runner-plan
                 :eda.murakumo/artifacts (:artifacts s)
                 :eda.murakumo/ready-adapters (mapv :eda.job.adapter/id
                                                     (filter #(= (:eda.job.adapter/status %) "ready") (:eda.job/adapters runner-plan)))
                 :eda.murakumo/events-path (str "/v1/eda/runs/" run-id "/events")}]
    (swap! state assoc :murakumo-payload payload)
    (transact! "eda.murakumo/submit-payload" {:run-id run-id :ready-adapters (count (:eda.murakumo/ready-adapters payload))
                                               :mode (:eda.murakumo/mode payload)})
    (proposal! "Murakumo submit payload built. This is a dry-run payload until a host runner receives policy approval." "info")
    payload))

(defn run-co-sientist-review! []
  (let [co (co-sientist-review @state)]
    (swap! state assoc :co co)
    (transact! "eda.review/co-sientist" {:quality (:quality co) :uiux (:uiux co)
                                          :gate-coverage (js/Number (.toFixed (* (:gate-coverage co) 100) 1))
                                          :findings (count (:findings co))})
    (proposal! "Co-sientist reviewed quality and UIUX. Results are proposal-only and cannot approve signoff." "info")))

(defn run-maturity-audit! []
  (let [m (maturity-assessment @state)]
    (swap! state assoc :maturity m)
    (transact! "eda.maturity/audit" {:level (:level m) :readiness (:readiness m) :simulation-coverage (:sim-coverage m)
                                      :blockers (count (filter #(= (:status %) "block") (:checks m)))})
    (proposal! "Maturity audit updated manufacturing readiness, simulation coverage, evidence CIDs and blockers." "info")))

(defn run-stage! []
  (let [s @state
        c (cfg s)
        [id name] (nth stages (:stage s))
        cid (edn-hash (->json {:id id :c c :stage (:stage s) :issue (:issue s)}))
        status (if (and (:issue s) (>= (:stage s) 6) (< (:stage s) 8)) "blocked" "passed")]
    (transact! "eda.run/complete" {:tool (str "murakumo." id) :status status :cid cid})
    (if (= status "blocked")
      (do (transact! "eda.report/finding" {:severity "high" :rule "timing-drc-correlation" :cid (edn-hash (str "finding" cid))})
          (proposal! "STA と DRC overlay の相関から、clock spine 近傍の keepout と buffer sizing を見直す proposal を生成しました。" "warn"))
      (do (proposal! (str name " completed. LLM は report 要約と次工程 plan の proposal のみを保存しました。"))
          (when (< (:stage s) (dec (count stages))) (swap! state update :stage inc))))))

(defn run-all! []
  (loop [guard 0]
    (let [s @state]
      (when (and (< (:stage s) (dec (count stages))) (< guard 20))
        (run-stage!)
        (let [s' @state]
          (when-not (and (:issue s') (>= (:stage s') 6) (< (:stage s') 8))
            (recur (inc guard))))))))

(defn toggle-issue! []
  (let [was (:issue @state)]
    (swap! state assoc :issue (if was nil "timing-drc-correlation"))
    (transact! "eda.issue/toggle" {:issue (or (:issue @state) "cleared")})
    (proposal! (if was "issue を解除しました。" "意図的な signoff issue を追加しました。DRC/LVS/STA の gate で止まります。")
               (if was "info" "warn"))))

(defn approve-gate! [id]
  (swap! state update :approvals conj id)
  (transact! "eda.policy/approve" {:gate id :approver "human"}))

(defn load-sample-signoff! []
  (doseq [row (signoff-evidence-template)]
    (let [evidence (normalize-evidence row)]
      (swap! state update :signoff-evidence #(cons evidence %))
      (swap! state update :runner-results
             #(cons {:adapter (:type evidence) :tool (:tool evidence) :operation (:operation evidence)
                      :status (:status evidence) :coverage (:coverage evidence) :output-cid (:output-cid evidence)}
                     %))
      (transact! "eda.signoff/evidence" evidence)))
  (proposal! "Sample OpenSTA/OpenROAD/KLayout/Netgen/ngspice/ATE signoff evidence loaded. Release-ready still requires foundry-slot and human-signoff approvals." "info"))

(defn signoff-evidence-template []
  [{:type "signoff/timing-pvt" :tool "sw/opensta" :operation "op/analyze-timing" :status "passed" :coverage 96
    :corners 4 :corner "ss_0p72v_125c" :pvt "ss/0.72V/125C" :slack-ns 0.041 :output-cid (edn-hash "opensta-pvt")}
   {:type "signoff/route" :tool "sw/openroad" :operation "op/route" :status "passed" :coverage 92
    :overflow 0 :output-cid (edn-hash "openroad-route")}
   {:type "signoff/drc" :tool "sw/klayout" :operation "op/drc" :status "passed" :coverage 100
    :violations 0 :rule-deck-cid (edn-hash "klayout-deck") :output-cid (edn-hash "klayout-drc")}
   {:type "signoff/lvs" :tool "sw/netgen" :operation "op/lvs" :status "passed" :coverage 100
    :mismatches 0 :output-cid (edn-hash "netgen-lvs")}
   {:type "signoff/spice-corner" :tool "sw/ngspice" :operation "op/simulate" :status "passed" :coverage 88
    :corner "tt_1p8v_25c" :output-cid (edn-hash "ngspice-corner")}
   {:type "signoff/ate-pattern" :tool "sw/ate-adapter" :operation "op/ate" :status "passed" :coverage 97
    :vector-coverage 97 :output-cid (edn-hash "ate-pattern")}])

;; -- canvas / render-IR -------------------------------------------------------

(defn make-render-ir [s c sc]
  (let [dies (map-indexed
              (fn [i ip]
                {:id (str "macro-" ip)
                 :layer (case (mod i 3) 0 "M1" 1 "M4" "Mtop")
                 :x (+ 90 (* (mod i 3) 210))
                 :y (+ 90 (* (quot i 3) 140))
                 :w (+ 140 (if (= ip "ml") 70 0))
                 :h (+ 80 (if (= ip "sram") 45 0))
                 :color (nth ["#2563eb" "#16825d" "#c2410c" "#0891b2" "#6d28d9" "#b45309"] (mod i 6))})
              (:ip c))]
    {:frame/n (:stage s) :frame/clear [0.97 0.98 0.99 1.0] :frame/kami-engine "render-ir-compatible"
     :eda/project (:target c) :eda/process (:process c) :eda/stage (first (nth stages (:stage s)))
     :eda/signoff (js/Number (.toFixed (* (:signoff sc) 100) 1))
     :eda/yield (js/Number (.toFixed (:yield-pct sc) 1))
     :eda/co-sientist (or (:co s) (co-sientist-review s))
     :eda/maturity (or (:maturity s) (maturity-assessment s))
     :eda/coverage (coverage-assessment s)
     :frame/passes [{:pass/id "eda-main" :pass/target "canvas"
                      :pass/draws (mapv (fn [d] {:draw/pipeline "eda-layer-rect" :draw/mesh "rect"
                                                   :draw/material (:layer d)
                                                   :draw/instances {:count 1 :rect [(:x d) (:y d) (:w d) (:h d)]
                                                                     :tint (:color d) :label (:id d)}})
                                         dies)}]}))

(defn canvas-ctx []
  (some-> (.getElementById js/document "eda-canvas") (.getContext "2d")))

(defn font-family []
  (.-fontFamily (js/getComputedStyle (.-body js/document))))

(defn draw-layout! [ctx ir]
  (let [canvas (.-canvas ctx)]
    (.clearRect ctx 0 0 (.-width canvas) (.-height canvas))
    (set! (.-fillStyle ctx) "#e5eaf2") (.fillRect ctx 0 0 (.-width canvas) (.-height canvas))
    (set! (.-fillStyle ctx) "#f8fafc") (set! (.-strokeStyle ctx) "#334155") (set! (.-lineWidth ctx) 2)
    (.fillRect ctx 60 60 700 430) (.strokeRect ctx 60 60 700 430)
    (doseq [draw (:pass/draws (first (:frame/passes ir)))]
      (let [[x y w h] (:rect (:draw/instances draw))]
        (set! (.-fillStyle ctx) (:tint (:draw/instances draw)))
        (set! (.-globalAlpha ctx) 0.82)
        (.fillRect ctx x y w h)
        (set! (.-globalAlpha ctx) 1)
        (set! (.-strokeStyle ctx) "#0f172a") (.strokeRect ctx x y w h)
        (set! (.-fillStyle ctx) "#fff") (set! (.-font ctx) (str "18px " (font-family)))
        (.fillText ctx (:label (:draw/instances draw)) (+ x 10) (+ y 28))))
    (set! (.-fillStyle ctx) "#172033") (set! (.-font ctx) (str "24px " (font-family)))
    (.fillText ctx (str "GDS/OASIS layout view · " (:eda/process ir)) 60 535)))

(defn draw-flow! [ctx s]
  (let [canvas (.-canvas ctx)]
    (.clearRect ctx 0 0 (.-width canvas) (.-height canvas))
    (set! (.-fillStyle ctx) "#f8fafc") (.fillRect ctx 0 0 (.-width canvas) (.-height canvas))
    (doseq [[i [id nm _]] (map-indexed vector stages)]
      (let [col (mod i 5) row (quot i 5) x (+ 55 (* col 200)) y (+ 70 (* row 155))
            stage (:stage s)]
        (set! (.-fillStyle ctx) (cond (< i stage) "#dcfce7" (= i stage) "#dbeafe" :else "#fff"))
        (set! (.-strokeStyle ctx) (if (= i stage) "#2563eb" "#cbd5e1"))
        (set! (.-lineWidth ctx) (if (= i stage) 3 1))
        (.fillRect ctx x y 155 74) (.strokeRect ctx x y 155 74)
        (set! (.-fillStyle ctx) "#172033") (set! (.-font ctx) (str "17px " (font-family)))
        (.fillText ctx nm (+ x 12) (+ y 32))
        (set! (.-fillStyle ctx) "#667085") (set! (.-font ctx) (str "12px " (font-family)))
        (.fillText ctx id (+ x 12) (+ y 54))))))

(defn draw-wafer! [ctx s]
  (let [canvas (.-canvas ctx)
        c (cfg s) sc (score c s)]
    (.clearRect ctx 0 0 (.-width canvas) (.-height canvas))
    (set! (.-fillStyle ctx) "#eef2f7") (.fillRect ctx 0 0 (.-width canvas) (.-height canvas))
    (.beginPath ctx) (.arc ctx 360 310 230 0 (* js/Math.PI 2))
    (set! (.-fillStyle ctx) "#f8fafc") (.fill ctx) (set! (.-strokeStyle ctx) "#334155") (.stroke ctx)
    (doseq [y (range -7 8) x (range -7 8)]
      (when (< (+ (* x x) (* y y)) 49)
        (let [pass (< (mod (+ (mod (+ (* x 13) (* y 17) (* (:stage s) 11)) 100) 100) 100) (:yield-pct sc))]
          (set! (.-fillStyle ctx) (if pass "#16a34a" "#dc2626"))
          (.fillRect ctx (- (+ 360 (* x 27)) 10) (- (+ 310 (* y 27)) 10) 20 20))))
    (set! (.-fillStyle ctx) "#172033") (set! (.-font ctx) (str "26px " (font-family)))
    (.fillText ctx (str "Wafer sort yield " (.toFixed (:yield-pct sc) 1) "%") 650 210)
    (set! (.-font ctx) (str "16px " (font-family)))
    (.fillText ctx "Probe map and binning become :eda.manufacturing/probe datoms." 650 245)))

(defn draw-package! [ctx]
  (let [canvas (.-canvas ctx)]
    (.clearRect ctx 0 0 (.-width canvas) (.-height canvas))
    (set! (.-fillStyle ctx) "#f8fafc") (.fillRect ctx 0 0 (.-width canvas) (.-height canvas))
    (set! (.-fillStyle ctx) "#dbeafe") (set! (.-strokeStyle ctx) "#1d4ed8") (set! (.-lineWidth ctx) 3)
    (.fillRect ctx 250 210 520 230) (.strokeRect ctx 250 210 520 230)
    (set! (.-fillStyle ctx) "#172033") (.fillRect ctx 410 280 200 95)
    (set! (.-fillStyle ctx) "#fff") (set! (.-font ctx) (str "22px " (font-family))) (.fillText ctx "DIE" 488 335)
    (set! (.-strokeStyle ctx) "#b45309") (set! (.-lineWidth ctx) 2)
    (doseq [i (range 18)]
      (.beginPath ctx) (.moveTo ctx (+ 420 (* i 10)) 280) (.lineTo ctx (+ 280 (* i 28)) 210) (.stroke ctx))
    (set! (.-fillStyle ctx) "#172033") (set! (.-font ctx) (str "24px " (font-family)))
    (.fillText ctx "Package / assembly / thermal view" 250 500)))

(defn draw! []
  (let [ctx (canvas-ctx)
        s @state
        c (cfg s)
        sc (score c s)
        ir (make-render-ir s c sc)]
    (swap! state assoc :render-ir ir)
    (when ctx
      (case (:view s)
        "layout" (draw-layout! ctx ir)
        "flow" (draw-flow! ctx s)
        "wafer" (draw-wafer! ctx s)
        "package" (draw-package! ctx)
        nil))))

(defn packet [s]
  (let [c (cfg s) sc (score c s)]
    {:project (str "kotoba-eda-" (:target c)) :process (:process c) :stage (first (nth stages (:stage s)))
     :gates (mapv (fn [[id]] [id (contains? (:approvals s) id)]) gates)
     :artifact-count (count (:artifacts s))
     :artifacts {:source (edn-hash (str "source" (->json c))) :netlist (edn-hash (str "netlist" (->json c)))
                 :gds (edn-hash (str "gds" (->json c))) :reports (edn-hash (str "reports" (count (:datoms s))))
                 :waivers (edn-hash (str "waivers" (or (:issue s) "none")))}
     :manufacturing {:mask-order (if (and (contains? (:approvals s) "mask-budget") (contains? (:approvals s) "human-signoff")) "ready" "gated")
                      :foundry-upload (if (contains? (:approvals s) "foundry-slot") "ready" "gated")
                      :wafer-traveller ["lot-start" "implant" "metallization" "pcm" "probe"]
                      :package-bom ["substrate" "die-attach" "bond" "mold" "mark"]
                      :ate-coverage (js/Math.round (* (:signoff sc) 100))
                      :expected-yield (js/Number (.toFixed (:yield-pct sc) 1))}
     :maturity (or (:maturity s) (maturity-assessment s))
     :signoff-evidence (signoff-evidence-assessment s)
     :signoff-evidence-datoms (:signoff-evidence s)
     :artifact-manifests (:artifacts s)}))

;; -- reactive views ------------------------------------------------------

(defn project-panel []
  (let [s @state c (cfg s)]
    [:div.panel
     [:h2 "Project"]
     [:label "Target product"
      [:select {:value (:target s)
                :on-change (fn [e] (swap! state assoc :target (.. e -target -value))
                             (transact! "eda.project/update" (cfg @state)))}
       [:option {:value "sensor-asic"} "Sensor ASIC"]
       [:option {:value "edge-accelerator"} "Edge AI Accelerator"]
       [:option {:value "pmic"} "PMIC / BCD"]
       [:option {:value "mixed-signal"} "Mixed-signal Controller"]]]
     [:label "Process / PDK"
      [:select {:value (:process s)
                :on-change (fn [e] (swap! state assoc :process (.. e -target -value))
                             (transact! "eda.project/update" (cfg @state)))}
       [:option {:value "sky130"} "Sky130-like open PDK"]
       [:option {:value "gf180"} "GF180-like mixed signal"]
       [:option {:value "bcd180"} "180nm BCD"]
       [:option {:value "cmos28"} "28nm CMOS"]]]
     [:label "Die size " [:span#die-label (str (:die c) " mm²")]
      [:input {:type "range" :min 4 :max 144 :value (:die s)
               :on-change (fn [e] (swap! state assoc :die (js/Number (.. e -target -value)))
                            (transact! "eda.project/update" (cfg @state)))}]]
     [:label "Volume " [:span#volume-label (str (:volume c) "k units")]
      [:input {:type "range" :min 1 :max 1000 :value (:volume s)
               :on-change (fn [e] (swap! state assoc :volume (js/Number (.. e -target -value)))
                            (transact! "eda.project/update" (cfg @state)))}]]
     [:div.checks {:aria-label "IP blocks"}
      (for [[ip label] [["cpu" "RISC-V"] ["sram" "SRAM"] ["analog" "Analog macro"]
                         ["serdes" "SERDES"] ["ml" "ML array"] ["otp" "OTP"]]]
        ^{:key ip}
        [:label [:input {:type "checkbox" :checked (contains? (:ip s) ip)
                          :on-change (fn [_]
                                       (swap! state update :ip
                                              (fn [xs] (if (contains? xs ip) (disj xs ip) (conj xs ip))))
                                       (transact! "eda.project/update" (cfg @state)))}]
         (str " " label)])]]))

(defn stages-view []
  (let [s @state]
    [:div#stages.stage-grid
     (for [[i [id nm desc]] (map-indexed vector stages)]
       (let [klass (cond (< i (:stage s)) "stage done" (= i (:stage s)) "stage active" :else "stage")
             fail? (and (:issue s) (= i (:stage s)) (>= i 6))]
         ^{:key id}
         [:div {:class (str klass (when fail? " fail"))}
          [:b (str (inc i) ". " nm)] [:span desc] [:span.mono id]]))]))

(defn gates-view []
  (let [s @state]
    [:div#gates
     (for [[id nm desc] gates]
       (let [ok (contains? (:approvals s) id)]
         ^{:key id}
         [:div.gate
          [:div [:strong nm] [:span desc]]
          [:button {:on-click #(approve-gate! id)} (if ok "approved" "approve")]]))]))

(defn log-row [k label small trailing]
  ^{:key k} [:div.log-row [:b label] [:small small] trailing])

(defn datom-log-view []
  (let [s @state]
    [:div#datom-log.log
     (map-indexed (fn [i d]
                    (log-row i (:kind d)
                             (str (:time d) " · " (:stage d) " · " (or (:status d) (:gate d) (:cid d) ""))
                             nil))
                  (take 80 (:datoms s)))]))

(defn llm-log-view []
  (let [s @state]
    [:div#llm-log.log
     (map-indexed (fn [i d] (log-row i (:severity d) (:time d) (:text d))) (take 30 (:llm s)))]))

(defn artifact-log-view []
  (let [s @state
        artifacts (take 30 (:artifacts s))]
    [:div#artifact-log.log {:style {:margin-top "10px" :max-height "240px"}}
     (if (empty? artifacts)
       [:div.log-row [:b "empty"] [:small "Upload .sv, .sdc, .sp, .lib, .def, .gds, .vcd, .rpt and related EDA files."] "No artifacts ingested yet."]
       (map-indexed
        (fn [i a]
          (let [fields (str/join " " (map (fn [[k v]] (str (name k) ":" v)) (take 5 (:summary a))))]
            (log-row i (:format a) (str (:name a) " · " (:cid a)) fields)))
        artifacts))]))

(defn runner-log-view []
  (let [s @state
        plan (or (:runner-plan s) (build-preview-runner-plan s))]
    [:div#runner-log.log {:style {:margin-top "10px" :max-height "260px"}}
     (map-indexed
      (fn [i a]
        (log-row i (:eda.job.adapter/status a)
                 (str (:eda.job.adapter/id a) " · " (:eda.job.adapter/software a))
                 (:eda.job.adapter/name a)))
      (:eda.job/adapters plan))]))

(defn murakumo-log-view []
  (let [s @state payload (:murakumo-payload s)]
    [:div#murakumo-log.log {:style {:margin-top "10px" :max-height "180px"}}
     (if payload
       [:div.log-row [:b (:eda.murakumo/mode payload)]
        [:small (str (:eda.murakumo/run-id payload) " · " (:eda.murakumo/events-path payload))]
        (str (count (:eda.murakumo/ready-adapters payload)) " ready adapter(s)")]
       [:div.log-row [:b "empty"] [:small "Build a runner plan first, then build murakumo payload."] "No submit payload yet."])]))

(defn co-scores-view []
  (let [s @state co (or (:co s) (co-sientist-review s))]
    [:div#co-scores.score-list
     (for [[label value] [["Quality" (:quality co)] ["UIUX" (:uiux co)] ["Gates" (js/Math.round (* (:gate-coverage co) 100))]]]
       ^{:key label}
       [:div.score-row [:b label] [:div.bar [:span {:style {:width (str value "%")}}]] [:span (str value "%")]])]))

(defn co-findings-view []
  (let [s @state co (or (:co s) (co-sientist-review s))]
    [:div#co-findings.log {:style {:margin-top "10px" :max-height "220px"}}
     (map-indexed (fn [i [severity text]] (log-row i severity "co-sientist proposal" text)) (:findings co))]))

(defn maturity-cards-view []
  (let [s @state m (or (:maturity s) (maturity-assessment s))]
    [:div#maturity-cards.maturity-grid
     (for [[label value] [["Maturity" (:level m)] ["Readiness" (str (:readiness m) "%")] ["Simulation" (str (:sim-coverage m) "%")]]]
       ^{:key label} [:div.maturity-card [:span label] [:b value]])]))

(defn maturity-use-view []
  (let [s @state m (or (:maturity s) (maturity-assessment s))]
    [:div#maturity-use
     [:div.badges (for [x (:useable-for m)] ^{:key x} [:span.badge.ok x])]]))

(defn sim-matrix-view []
  (let [s @state m (or (:maturity s) (maturity-assessment s))]
    [:tbody#sim-matrix
     (map-indexed (fn [i [nm tool status coverage]]
                    ^{:key i} [:tr [:td nm] [:td tool] [:td status] [:td (str coverage "%")]])
                  (:sims m))]))

(defn readiness-log-view []
  (let [s @state m (or (:maturity s) (maturity-assessment s))]
    [:div#readiness-log.log {:style {:margin-top "10px" :max-height "260px"}}
     (map-indexed (fn [i x]
                    (log-row i (:status x) (str (:category x) " · " (:id x) " · " (or (:cid x) (:blocker x))) (:role x)))
                  (:checks m))]))

(defn coverage-cards-view []
  (let [s @state c (coverage-assessment s) signoff (signoff-evidence-assessment s)]
    [:div#coverage-cards.maturity-grid
     (for [[label value] [["Coverage" (str (:score c) "%")] ["Source" (:source c)]
                           ["Samples" (str (count (:runner-results s)))]
                           ["Signoff" (str (:passed signoff) "/" (:total signoff))]]]
       ^{:key label} [:div.maturity-card [:span label] [:b value]])]))

(defn coverage-matrix-view []
  (let [s @state c (coverage-assessment s)]
    [:tbody#coverage-matrix
     (map-indexed (fn [i r] ^{:key i} [:tr [:td (:id r)] [:td (:source r)] [:td (:status r)] [:td (str (:score r) "%")]])
                  (:rows c))]))

(defn signoff-evidence-matrix-view []
  (let [s @state signoff (signoff-evidence-assessment s)]
    [:tbody#signoff-evidence-matrix
     (map-indexed (fn [i r] ^{:key i} [:tr [:td (:label r)] [:td (:tool r)] [:td (:status r)] [:td (or (not-empty (:evidence r)) (:blocker r))]])
                  (:rows signoff))]))

(defn runner-result-log-view []
  (let [s @state results (take 20 (:runner-results s))]
    [:div#runner-result-log.log {:style {:margin-top "10px" :max-height "220px"}}
     (if (empty? results)
       [:div.log-row [:b "fallback"] [:small "stage-model"] "No runner result imported yet."]
       (map-indexed
        (fn [i r] (log-row i (:status r) (str (:tool r) " · " (:operation r) " · " (:output-cid r)) (str (:coverage r) "% coverage")))
        results))]))

(defn file-input [id accept multiple? on-files]
  [:input {:id id :type "file" :multiple multiple? :accept accept
           :on-change (fn [e]
                        (let [files (array-seq (.. e -target -files))]
                          (on-files files))
                        (set! (.. e -target -value) ""))}])

(defn artifact-intake-panel []
  [:div.panel
   [:h2 "Artifact Intake"]
   [:div.drop
    [:label "Upload EDA files"
     (file-input "artifact-files"
                  ".v,.sv,.svh,.vhd,.vhdl,.sp,.spi,.cir,.ckt,.cdl,.sdc,.upf,.lib,.lef,.def,.gds,.gdsii,.oas,.oasis,.vcd,.fst,.sdf,.saif,.stil,.wgl,.rpt,.log,.drc,.lvs,.rule,.rules,.deck"
                  true ingest-artifacts!)]]
   (artifact-log-view)])

(defn runner-adapter-panel []
  [:div.panel
   [:h2 "Runner Adapter"]
   [:p "ブラウザは EDN job plan を作るだけです。実行は host/murakumo runner が policy gate 後に行います。"]
   [:div.actions
    [:button.wide {:on-click (fn [_]
                                (let [plan (or (:runner-plan @state) (build-preview-runner-plan @state))]
                                  (download-text! "kotoba-eda-runner-plan.edn" (str (pr-str plan) "\n") "application/edn")))}
     "Download runner EDN"]
    [:button.wide {:on-click (fn [_] (build-murakumo-payload!))} "Build murakumo payload"]
    [:button.wide {:on-click (fn [_]
                                (let [payload (or (:murakumo-payload @state) (build-murakumo-payload!))]
                                  (download-text! "kotoba-eda-murakumo-submit.edn" (str (pr-str payload) "\n") "application/edn")))}
     "Download murakumo EDN"]]
   (runner-log-view) (murakumo-log-view)
   [:div.drop {:style {:margin-top "10px"}}
    [:label "Import runner result JSON" (file-input "runner-result-files" ".json" true import-runner-results!)]]
   [:div.drop {:style {:margin-top "10px"}}
    [:label "Import signoff evidence JSON" (file-input "signoff-evidence-files" ".json" true import-signoff-evidence!)]
    [:div.actions {:style {:margin-top "8px"}}
     [:button.wide {:on-click (fn [_] (load-sample-signoff!))} "Load sample signoff evidence"]
     [:button.wide {:on-click (fn [_]
                                 (download-text! "kotoba-eda-signoff-evidence-template.json"
                                                  (str (->json (signoff-evidence-template) 2) "\n")
                                                  "application/json"))}
      "Download evidence template"]]]
   [:div.source-links
    [:a {:href "https://github.com/kotoba-lang/eda"} "Native CLJC engine repo"]
    [:a {:href "https://kotoba-lang.github.io/eda/sample_flow.edn"} "Native EDN sample flow"]
    [:a {:href "https://kotoba-lang.github.io/eda/oss_manifest.edn"} "OSS report manifest"]
    [:a {:href "source.html?file=eda_runner_adapters.edn"} "Runner adapters EDN"]
    [:a {:href "source.html?file=kotoba_eda_runner.cljc"} "Runner CLJC"]
    [:a {:href "source.html?file=eda_signoff_evidence.edn"} "Signoff evidence EDN"]
    [:a {:href "source.html?file=eda_murakumo_job.edn"} "Murakumo job EDN"]
    [:a {:href "source.html?file=kotoba_eda_murakumo.cljc"} "Murakumo CLJC"]
    [:a {:href "source.html?file=kotoba_eda_app.cljs"} "UI reagent app"]
    [:a {:href "source.html?file=runner_host.clj"} "Host runner"]]])

(defn policy-gates-panel []
  [:div.panel [:h2 "Policy Gates"] (gates-view)])

(defn run-control-panel []
  [:div.panel
   [:h2 "Run Control"]
   [:div.actions
    [:button.primary.wide {:on-click (fn [_] (run-all!))} "Run full flow"]
    [:button {:on-click (fn [_] (run-stage!))} "Advance stage"]
    [:button.danger {:on-click (fn [_] (toggle-issue!))} "Inject issue"]
    [:button {:on-click (fn [_] (download-text! "kotoba-eda-datoms.json" (str (->json (:datoms @state) 2) "\n") "application/json"))}
     "Export datoms"]
    [:button {:on-click (fn [_] (download-text! "kotoba-eda-manufacturing-packet.json" (str (->json (packet @state) 2) "\n") "application/json"))}
     "Manufacturing packet"]
    [:button.wide {:on-click (fn [_] (run-co-sientist-review!))} "Run co-sientist review"]
    [:button.wide {:on-click (fn [_] (run-maturity-audit!))} "Run maturity audit"]
    [:button.wide {:on-click (fn [_] (build-runner-plan!))} "Build runner plan"]]])

(defn viewer-panel []
  (let [s @state]
    [:div.panel
     [:h2 "kami-engine Viewer"]
     [:div.canvas-wrap
      [:div.canvas-tabs
       (for [[view label] [["layout" "Layout"] ["flow" "Flow"] ["wafer" "Wafer"] ["package" "Package"]]]
         ^{:key view}
         [:button {:class (when (= (:view s) view) "active") :data-view view
                   :on-click (fn [_] (swap! state assoc :view view) (draw!))}
          label])]
      [:canvas#eda-canvas {:width 1080 :height 630 :data-kami-engine "render-ir"}]]]))

(defn manufacturing-readiness-panel []
  (let [s @state m (or (:maturity s) (maturity-assessment s))]
    [:div#manufacturing.panel
     [:h2 "Manufacturing Readiness"]
     [:p#mfg-summary (->json (:manufacturing (packet s)))]
     (maturity-cards-view) (maturity-use-view)
     [:table.matrix {:aria-label "Simulation matrix"}
      [:thead [:tr [:th "Simulation"] [:th "Tool"] [:th "Status"] [:th "Coverage"]]]
      (sim-matrix-view)]
     (readiness-log-view)]))

(defn coverage-panel []
  [:div#coverage.panel
   [:h2 "Coverage"]
   [:p "Runner results, uploaded reports, and stage-model fallback are separated as " [:code ":eda.coverage/*"] " data."]
   (coverage-cards-view)
   [:table.matrix {:aria-label "Coverage matrix"}
    [:thead [:tr [:th "Metric"] [:th "Source"] [:th "Status"] [:th "Score"]]]
    (coverage-matrix-view)]
   [:h3 "Signoff Evidence Gates"]
   [:table.matrix {:aria-label "Signoff evidence matrix"}
    [:thead [:tr [:th "Gate"] [:th "Tool"] [:th "Status"] [:th "Evidence"]]]
    (signoff-evidence-matrix-view)]
   (runner-result-log-view)
   [:div.source-links
    [:a {:href "source.html?file=eda_coverage_schema.edn"} "Coverage schema EDN"]
    [:a {:href "source.html?file=eda_signoff_evidence.edn"} "Signoff evidence EDN"]]])

(defn formats-panel []
  [:div#formats.panel
   [:h2 "File Format Registry"]
   [:p "EDA artifacts are CID-addressed files with EDN manifests. Each format maps to software adapters, operations, policy gates and EDN-centered converter pipelines."]
   [:div.badges
    [:span.badge.ok ".v .sv .vhd"] [:span.badge.ok ".sp .cdl .sdc .upf"] [:span.badge.ok ".lib .lef .def"]
    [:span.badge.warn ".gds .oas"] [:span.badge.warn ".vcd .fst .sdf .saif"] [:span.badge.stop ".stil .wgl .deck"]]
   [:div.log {:style {:margin-top "10px" :max-height "210px"}}
    [:div.log-row [:b "RTL"] [:small ".v/.sv/.vhd -> EDN RTL graph -> Yosys/Surelog/slang/GHDL -> synth/sim/formal"]]
    [:div.log-row [:b "Analog"] [:small ".sp/.cdl -> EDN netlist -> ngspice/Xyce/Netgen -> sim/LVS"]]
    [:div.log-row [:b "Physical"] [:small ".lib/.lef/.def/.gds/.oas -> EDN physical model -> OpenROAD/KLayout/Magic/OpenSTA -> P&R/signoff/tapeout"]]
    [:div.log-row [:b "Analysis"] [:small ".vcd/.fst/.sdf/.saif/.rpt -> EDN summaries/findings -> kami render-IR and LLM proposal input"]]
    [:div.log-row [:b "Manufacturing"] [:small ".stil/.wgl + GDS/OASIS + reports -> EDN release packet -> ATE/foundry handoff gates"]]]
   [:div.source-links
    [:a {:href "source.html?file=eda_file_formats.edn"} "Canonical EDN registry"]
    [:a {:href "source.html?file=kotoba_eda_formats.cljc"} "Pure CLJC query layer"]]])

(defn proposal-panel [] [:div.panel [:h2 "LLM / murakumo Proposals"] (llm-log-view)])
(defn co-sientist-panel [] [:div.panel [:h2 "Co-sientist Quality"] (co-scores-view) (co-findings-view)])
(defn datom-panel [] [:div.panel [:h2 "Datom Log"] (datom-log-view)])
(defn render-ir-panel []
  (let [s @state]
    [:div.panel [:h2 "render-IR"] [:pre#render-ir (some-> (:render-ir s) (->json 2))]]))

(defn hero []
  (let [s @state c (cfg s) sc (score c s)]
    [:section.hero {:aria-labelledby "title"}
     [:div.panel
      [:h1#title "kotoba EDA Flow Workbench"]
      [:p "ブラウザ内で半導体の要求、設計、検証、サインオフ、製造引き渡しまでを一つの流れとして操作する実験版です。正本は "
       [:code ".cljc"] " の純粋データモデルで、描画面は kami-engine の render-IR 形状に寄せています。"]
      [:div.badges
       [:span.badge.ok "CLJC workflow model"] [:span.badge.ok "kami render-IR"]
       [:span.badge.warn "LLM proposals only"] [:span.badge.stop "Foundry upload requires gate"]]]
     [:div.panel
      [:h2 "Current Run"]
      [:div.metrics
       [:div.metric [:span "Stage"] [:b#metric-stage (second (nth stages (:stage s)))]]
       [:div.metric [:span "Signoff"] [:b#metric-signoff (str (js/Math.round (* (:signoff sc) 100)) "%")]]
       [:div.metric [:span "Yield"] [:b#metric-yield (str (.toFixed (:yield-pct sc) 1) "%")]]
       [:div.metric [:span "Cost"] [:b#metric-cost (str "$" (:cost sc) "k")]]]
      [:div.source-links
       [:a {:href "source.html?file=kotoba_eda_core.cljc"} "CLJC model"]
       [:a {:href "source.html?file=eda_file_formats.edn"} "EDA formats EDN"]
       [:a {:href "source.html?file=kotoba_eda_formats.cljc"} "formats CLJC"]
       [:a {:href "source.html?file=kami_render_ir.edn"} "render-IR sample"]
       [:a {:href "../ADR-kotoba-eda-web-semiconductor-app.edn"} "ADR EDN"]]]]))

(defn workspace []
  [:section#flow.workspace
   [:aside.stack (project-panel) (run-control-panel) (artifact-intake-panel) (runner-adapter-panel) (policy-gates-panel)]
   [:section.stack (viewer-panel) (stages-view) (manufacturing-readiness-panel) (coverage-panel) (formats-panel)]
   [:aside.stack (proposal-panel) (co-sientist-panel) (datom-panel) (render-ir-panel)]])

(defn root []
  [:<> (hero) (workspace)])

;; -- canvas redraw lifecycle ---------------------------------------------
;; Reagent re-renders `root` on every state change, but the canvas 2D
;; context needs an imperative redraw after each commit — a plain
;; component-did-update watcher on the mount, same trigger point
;; `refresh()`'s trailing `draw()` call used in the original.

(defn watch-and-draw! []
  (add-watch state ::draw (fn [_ _ _ _] (js/requestAnimationFrame draw!))))

(defn ^:export init! []
  (rdom/render [root] (.getElementById js/document "app"))
  (watch-and-draw!)
  (set! (.-__kotobaEda js/window)
        #js {:state state :buildRunnerPlan build-runner-plan! :buildMurakumoPayload build-murakumo-payload!
             :buildPreviewRunnerPlan (fn [] (clj->js (build-preview-runner-plan @state)))
             :packet (fn [] (clj->js (packet @state))) :toEdn pr-str
             :signoffEvidenceAssessment (fn [] (clj->js (signoff-evidence-assessment @state)))
             :signoffEvidenceTemplate (fn [] (clj->js (signoff-evidence-template)))})
  (transact! "eda.project/create" (cfg @state))
  (proposal! "murakumo inference queue is ready. LLM output is stored as :eda.review/* proposal data, not as signoff authority.")
  (draw!))

(defonce _init (init!))
