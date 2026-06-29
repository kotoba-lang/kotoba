(ns kotoba.eda.core
  "Portable CLJC model for the kotoba EDA web workbench.

  The browser page in docs/eda/index.html mirrors these pure functions. The data
  shape follows kami.render/frame: immutable maps, explicit draw passes, and no
  renderer-owned truth. Real EDA tools stay behind adapters; this namespace
  models the workflow, datoms, gates, artifact CIDs and manufacturing handoff."
  #?(:cljs (:require [cljs.reader :as reader])))

(def stages
  [{:stage/id :spec     :stage/name "Spec"          :stage/role "requirements, IO, clocks, power, test intent"}
   {:stage/id :arch     :stage/name "Architecture"  :stage/role "IP blocks, buses, memories, analog boundaries"}
   {:stage/id :source   :stage/name "Source"        :stage/role ".kotoba, .cljc, RTL, SPICE, constraints"}
   {:stage/id :sim      :stage/name "Simulation"    :stage/role "unit, mixed-signal, waveform, formal checks"}
   {:stage/id :synth    :stage/name "Synthesis"     :stage/role "netlist, timing constraints, area and power"}
   {:stage/id :pnr      :stage/name "Floorplan/P&R" :stage/role "placement, routing, congestion, clocks"}
   {:stage/id :signoff  :stage/name "Signoff"       :stage/role "DRC, LVS, STA, IR, EM, SPICE reports"}
   {:stage/id :tapeout  :stage/name "Tapeout"       :stage/role "GDS/OASIS, LEF/DEF, netlist and waiver bundle"}
   {:stage/id :mask     :stage/name "Mask order"    :stage/role "reticle plan, mask shop package, release gate"}
   {:stage/id :wafer    :stage/name "Wafer lot"     :stage/role "process traveller, PCM, lot sampling"}
   {:stage/id :probe    :stage/name "Probe"         :stage/role "wafer sort, binning, known-good die data"}
   {:stage/id :package  :stage/name "Package"       :stage/role "assembly, substrate, wirebond/flip-chip, thermal"}
   {:stage/id :final    :stage/name "Final test"    :stage/role "ATE vectors, QA, yield ramp, ship release"}])

(def gates
  [{:gate/id :pdk-license   :gate/name "PDK license"   :gate/role "PDK and rule deck usage rights"}
   {:gate/id :nda-export    :gate/name "NDA / export"  :gate/role "external inference and foundry transfer policy"}
   {:gate/id :mask-budget   :gate/name "Mask budget"   :gate/role "paid mask order authorization"}
   {:gate/id :foundry-slot  :gate/name "Foundry slot"  :gate/role "lot reservation and upload window"}
   {:gate/id :human-signoff :gate/name "Human signoff" :gate/role "responsible approval, never LLM-owned"}])

(def co-sientist-checks
  [{:check/id :quality/spec-coverage
    :check/name "Spec coverage"
    :check/role "requirements, interfaces, clocks, power domains and test intent are explicit"}
   {:check/id :quality/signoff-evidence
    :check/name "Signoff evidence"
    :check/role "DRC/LVS/STA/SPICE/ATE artifacts have CIDs and policy gates"}
   {:check/id :quality/reproducibility
    :check/name "Reproducibility"
    :check/role "tool versions, inputs, outputs and waiver decisions are replayable"}
   {:check/id :uiux/operator-scan
    :check/name "Operator scan"
    :check/role "stage, risk, next action and blocking gate are visible without reading logs"}
   {:check/id :uiux/error-recovery
    :check/name "Error recovery"
    :check/role "blocked flow gives a concrete next proposal and preserves prior artifacts"}
   {:check/id :uiux/source-access
    :check/name "Source access"
    :check/role "CLJC/EDN source and format registry open in-browser, not as accidental downloads"}])

(def readiness-checks
  [{:readiness/id :design/spec-reviewed
    :readiness/category :design
    :readiness/required-stage :arch
    :readiness/role "requirements, interfaces and power/timing intent reviewed"}
   {:readiness/id :design/source-frozen
    :readiness/category :design
    :readiness/required-stage :source
    :readiness/role ".kotoba/.cljc/RTL/SPICE sources have CIDs"}
   {:readiness/id :simulation/rtl
    :readiness/category :simulation
    :readiness/required-stage :sim
    :readiness/role "RTL/unit regression and waveform summary available"}
   {:readiness/id :simulation/mixed-signal
    :readiness/category :simulation
    :readiness/required-stage :sim
    :readiness/role "SPICE or mixed-signal corner smoke tests available"}
   {:readiness/id :implementation/synthesis
    :readiness/category :implementation
    :readiness/required-stage :synth
    :readiness/role "synthesis reports, netlist and constraints are reproducible"}
   {:readiness/id :implementation/pnr
    :readiness/category :implementation
    :readiness/required-stage :pnr
    :readiness/role "DEF, congestion, clock and route reports are reproducible"}
   {:readiness/id :signoff/drc-lvs-sta
    :readiness/category :signoff
    :readiness/required-stage :signoff
    :readiness/role "DRC/LVS/STA evidence CIDs are present and current"}
   {:readiness/id :release/tapeout-bundle
    :readiness/category :release
    :readiness/required-stage :tapeout
    :readiness/role "GDS/OASIS, waiver manifest and release packet exist"}
   {:readiness/id :manufacturing/mask-gated
    :readiness/category :manufacturing
    :readiness/required-stage :mask
    :readiness/role "mask order is explicit, budgeted and human-approved"}
   {:readiness/id :manufacturing/probe-package-ate
    :readiness/category :manufacturing
    :readiness/required-stage :final
    :readiness/role "probe, package and final ATE plans are traceable"}])

(def artifact-evidence-map
  {:rtl/verilog [:design/source-frozen :simulation/rtl]
   :rtl/systemverilog [:design/source-frozen :simulation/rtl]
   :rtl/vhdl [:design/source-frozen :simulation/rtl]
   :analog/spice [:design/source-frozen :simulation/mixed-signal]
   :analog/cdl [:simulation/mixed-signal :signoff/drc-lvs-sta]
   :constraint/sdc [:design/spec-reviewed :implementation/synthesis]
   :constraint/upf [:design/spec-reviewed]
   :library/liberty [:implementation/synthesis :signoff/drc-lvs-sta]
   :physical/lef [:implementation/pnr]
   :physical/def [:implementation/pnr]
   :layout/gdsii [:release/tapeout-bundle :manufacturing/mask-gated]
   :layout/oasis [:release/tapeout-bundle :manufacturing/mask-gated]
   :wave/vcd [:simulation/rtl]
   :wave/fst [:simulation/rtl]
   :timing/sdf [:signoff/drc-lvs-sta]
   :power/saif [:signoff/drc-lvs-sta]
   :test/stil [:manufacturing/probe-package-ate]
   :test/wgl [:manufacturing/probe-package-ate]
   :report/generic [:signoff/drc-lvs-sta]
   :pdk/rule-deck [:signoff/drc-lvs-sta]})

(def default-project
  {:eda.project/id :kotoba-eda-demo
   :eda.project/target :sensor-asic
   :eda.project/process :sky130
   :eda.project/die-mm2 16
   :eda.project/volume-k 25
   :eda.project/ip #{:cpu :sram :otp}
   :eda.project/stage 0
   :eda.project/approvals #{:pdk-license}
   :eda.project/issue nil})

(defn stable-cid
  "Deterministic browser-safe placeholder CID. Production swaps this for kotoba
  object-store CID creation."
  [x]
  (let [s (pr-str x)
        h (reduce (fn [h ch]
                    (mod (* 16777619 (bit-xor h (int ch))) 4294967296))
                  2166136261
                  s)]
    (str "bafyeda" #?(:clj (Long/toString h 36)
                      :cljs (.toString h 36)))))

(defn stage-score
  [{:eda.project/keys [die-mm2 process ip stage issue volume-k]}]
  (let [complexity (+ (/ die-mm2 144.0)
                      (* 0.055 (count ip))
                      (case process
                        :cmos28 0.18
                        :bcd180 0.10
                        0.0))
        issue-penalty (if issue 0.08 0.0)
        signoff (-> (/ stage (dec (count stages)))
                    (- issue-penalty)
                    (max 0.0)
                    (min 1.0))
        yield (-> (- 96.0 (* complexity 18.0) (* issue-penalty 100.0))
                  (+ (* signoff 4.0))
                  (max 42.0)
                  (min 98.0))
        cost (Math/round (* (+ (* die-mm2 2.8)
                               (* volume-k 0.18)
                               (* (count ip) 8))
                            (case process
                              :cmos28 4.5
                              :bcd180 2.2
                              1.0)))]
    {:eda.score/complexity complexity
     :eda.score/signoff signoff
     :eda.score/yield yield
     :eda.score/cost-k cost}))

(defn current-stage [project]
  (nth stages (:eda.project/stage project 0)))

(defn datom
  [project kind attrs]
  (merge {:db/id (stable-cid [kind attrs])
          :eda.datom/kind kind
          :eda.stage/id (:stage/id (current-stage project))}
         attrs))

(defn artifact-manifest
  [{:keys [path format bytes sha256 cid]}]
  {:eda.artifact/path path
   :eda.artifact/format format
   :eda.artifact/bytes bytes
   :eda.artifact/sha256 sha256
   :eda.artifact/cid (or cid (stable-cid [path format bytes sha256]))
   :eda.artifact/evidence (get artifact-evidence-map format [])})

(defn run-stage
  [project]
  (let [stage (current-stage project)
        blocked? (and (:eda.project/issue project)
                      (<= 6 (:eda.project/stage project) 7))
        cid (stable-cid [(:stage/id stage) project])
        report (datom project :eda.run/complete
                      {:eda.run/tool (keyword "murakumo" (name (:stage/id stage)))
                       :eda.run/status (if blocked? :blocked :passed)
                       :eda.run/output-cid cid})
        next-project (if blocked?
                       project
                       (update project :eda.project/stage #(min (dec (count stages)) (inc %))))]
    {:project next-project
     :datoms (cond-> [report]
               blocked? (conj (datom project :eda.report/finding
                                      {:eda.report/severity :high
                                       :eda.report/rule :timing-drc-correlation
                                       :eda.report/cid (stable-cid [:finding cid])})))
     :review {:eda.review/kind :llm-proposal
              :eda.review/authority? false
              :eda.review/text (if blocked?
                                 "Correlate STA critical path with DRC overlay near clock spine before tapeout."
                                 (str (:stage/name stage) " completed; continue to next gate."))}}))

(defn run-flow
  [project]
  (loop [p project
         acc-datoms []
         reviews []
         guard 0]
    (if (or (= (:eda.project/stage p) (dec (count stages)))
            (>= guard 20))
      {:project p :datoms acc-datoms :reviews reviews}
      (let [{next-project :project
             step-datoms :datoms
             review :review} (run-stage p)
            next-datoms (into acc-datoms step-datoms)
            next-reviews (conj reviews review)]
        (if (= p next-project)
          {:project next-project :datoms next-datoms :reviews next-reviews}
          (recur next-project next-datoms next-reviews (inc guard)))))))

(defn manufacturing-packet
  [project]
  (let [score (stage-score project)
        approvals (:eda.project/approvals project)]
    {:eda.release/project (:eda.project/id project)
     :eda.release/stage (:stage/id (current-stage project))
     :eda.release/artifacts {:source (stable-cid [:source project])
                             :netlist (stable-cid [:netlist project])
                             :gds (stable-cid [:gds project])
                             :reports (stable-cid [:reports project])
                             :waivers (stable-cid [:waivers (:eda.project/issue project)])}
     :eda.manufacturing/mask-order (if (and (approvals :mask-budget)
                                            (approvals :human-signoff))
                                     :ready
                                     :gated)
     :eda.manufacturing/foundry-upload (if (approvals :foundry-slot) :ready :gated)
     :eda.manufacturing/wafer-traveller [:lot-start :implant :metallization :pcm :probe]
     :eda.manufacturing/package-bom [:substrate :die-attach :bond :mold :mark]
     :eda.manufacturing/ate-coverage (Math/round (* 100 (:eda.score/signoff score)))
     :eda.manufacturing/expected-yield (:eda.score/yield score)}))

(defn- stage-index
  [stage-id]
  (or (first (keep-indexed (fn [i s] (when (= stage-id (:stage/id s)) i)) stages))
      0))

(defn readiness-evidence
  ([project] (readiness-evidence project []))
  ([project artifacts]
  (let [stage (:eda.project/stage project 0)
        approvals (:eda.project/approvals project)
        evidence? (fn [id]
                    (some #(some #{id} (:eda.artifact/evidence %)) artifacts))]
    (mapv (fn [check]
            (let [required (stage-index (:readiness/required-stage check))
                  stage-ok? (>= stage required)
                  artifact-ok? (boolean (evidence? (:readiness/id check)))
                  gate-ok? (case (:readiness/id check)
                             :manufacturing/mask-gated (and (approvals :mask-budget)
                                                            (approvals :human-signoff))
                             true)
                  ok? (and (or stage-ok? artifact-ok?) gate-ok? (not (:eda.project/issue project)))]
              (assoc check
                     :readiness/status (if ok? :pass :block)
                     :readiness/evidence-cid
                     (when ok?
                       (or (:eda.artifact/cid (first (filter #(some #{(:readiness/id check)}
                                                                     (:eda.artifact/evidence %))
                                                              artifacts)))
                           (stable-cid [(:readiness/id check) project])))
                     :readiness/blocker
                     (cond
                       (:eda.project/issue project) :blocked-by-signoff-issue
                       (not (or stage-ok? artifact-ok?)) :stage-or-evidence-missing
                       (not gate-ok?) :policy-gate-missing
                       :else nil))))
          readiness-checks))))

(defn simulation-matrix
  [project]
  (let [score (stage-score project)
        stage (:eda.project/stage project 0)
        ip (:eda.project/ip project)
        sim-reached? (>= stage (stage-index :sim))
        signoff-reached? (>= stage (stage-index :signoff))]
    [{:sim/id :sim/rtl-unit
      :sim/tool :sw/verilator
      :sim/input [:rtl/systemverilog :constraint/sdc]
      :sim/output [:wave/vcd :report/generic]
      :sim/status (if sim-reached? :pass :pending)
      :sim/coverage (if sim-reached? (min 98 (Math/round (+ 72 (* 20 (:eda.score/signoff score))))) 0)}
     {:sim/id :sim/formal-smoke
      :sim/tool :sw/yosys
      :sim/input [:rtl/verilog :rtl/systemverilog]
      :sim/output [:report/generic]
      :sim/status (if sim-reached? :pass :pending)
      :sim/coverage (if sim-reached? 68 0)}
     {:sim/id :sim/mixed-signal
      :sim/tool :sw/ngspice
      :sim/input [:analog/spice :analog/cdl]
      :sim/output [:report/generic]
      :sim/status (cond
                    (not (some #{:analog} ip)) :not-applicable
                    sim-reached? :pass
                    :else :pending)
      :sim/coverage (cond
                      (not (some #{:analog} ip)) 100
                      sim-reached? 61
                      :else 0)}
     {:sim/id :sim/timing-corners
      :sim/tool :sw/opensta
      :sim/input [:library/liberty :constraint/sdc :timing/sdf]
      :sim/output [:report/generic]
      :sim/status (if signoff-reached? :pass :pending)
      :sim/coverage (if signoff-reached? 84 0)}
     {:sim/id :sim/power-activity
      :sim/tool :sw/opensta
      :sim/input [:power/saif :library/liberty]
      :sim/output [:report/generic]
      :sim/status (if signoff-reached? :pass :pending)
      :sim/coverage (if signoff-reached? 76 0)}]))

(defn maturity-assessment
  ([project] (maturity-assessment project []))
  ([project artifacts]
  (let [evidence (readiness-evidence project artifacts)
        passed (count (filter #(= :pass (:readiness/status %)) evidence))
        total (count evidence)
        ratio (/ passed (double total))
        sims (simulation-matrix project)
        sim-coverage (Math/round (/ (reduce + (map :sim/coverage sims)) (double (count sims))))
        approvals (:eda.project/approvals project)
        score (stage-score project)
        level (cond
                (and (= passed total)
                     (>= sim-coverage 85)
                     (approvals :foundry-slot)
                     (approvals :human-signoff)) :mrl/release-ready
                (and (>= ratio 0.8) (>= sim-coverage 75)) :mrl/pilot-ready
                (and (>= ratio 0.55) (>= sim-coverage 50)) :mrl/engineering-ready
                (>= ratio 0.3) :mrl/prototype
                :else :mrl/concept)
        blockers (->> evidence
                      (filter #(= :block (:readiness/status %)))
                      (mapv #(select-keys % [:readiness/id :readiness/category :readiness/blocker])))]
    {:eda.maturity/level level
     :eda.maturity/pass-count passed
     :eda.maturity/total total
     :eda.maturity/readiness-score (Math/round (* 100 ratio))
     :eda.maturity/simulation-coverage sim-coverage
     :eda.maturity/signoff (:eda.score/signoff score)
     :eda.maturity/evidence evidence
     :eda.maturity/simulations sims
     :eda.maturity/blockers blockers
     :eda.maturity/useable-for
     (case level
       :mrl/release-ready [:foundry-handoff :mask-order :pilot-lot :ate-release]
       :mrl/pilot-ready [:internal-tapeout-review :mpw-precheck :package-planning]
       :mrl/engineering-ready [:design-review :simulation-regression :pnr-iteration]
       :mrl/prototype [:architecture-review :source-bringup :testbench-work]
       [:requirements-work])})))

(defn co-sientist-review
  "Proposal-only quality/UIUX review. This is deliberately pure data; it never
  approves signoff and never mutates project state by itself."
  [project]
  (let [score (stage-score project)
        stage-ratio (:eda.score/signoff score)
        issue? (boolean (:eda.project/issue project))
        approvals (:eda.project/approvals project)
        gate-ratio (/ (count approvals) (double (count gates)))
        quality (-> (+ (* 55 stage-ratio)
                       (* 25 gate-ratio)
                       (if issue? -18 10)
                       (if (>= (:eda.project/die-mm2 project) 100) -4 6))
                    (max 0)
                    (min 100)
                    Math/round)
        uiux (-> (+ 72
                    (* 8 gate-ratio)
                    (if issue? -10 4)
                    (if (>= stage-ratio 0.5) 6 0))
                 (max 0)
                 (min 100)
                 Math/round)
        findings (cond-> []
                   (< quality 70) (conj {:finding/id :finding/quality-gate
                                          :finding/severity :high
                                          :finding/text "Add missing evidence CIDs before release or foundry handoff."})
                   issue? (conj {:finding/id :finding/blocked-signoff
                                  :finding/severity :high
                                  :finding/text "Resolve timing/DRC correlation before tapeout."})
                   (< gate-ratio 0.8) (conj {:finding/id :finding/policy-gates
                                             :finding/severity :medium
                                             :finding/text "Approve remaining policy gates or keep vendor actions disabled."})
                   (< uiux 82) (conj {:finding/id :finding/operator-clarity
                                      :finding/severity :medium
                                      :finding/text "Promote next action, blocking gate and artifact status in the primary scan path."}))]
    {:eda.review/kind :co-sientist/quality-uiux
     :eda.review/authority? false
     :eda.review/checks co-sientist-checks
     :eda.review/scores {:quality quality :uiux uiux :gate-coverage gate-ratio}
     :eda.review/findings findings
     :eda.review/next-actions
     (if (seq findings)
       (mapv :finding/text findings)
       ["Quality and UIUX review is clean enough to continue to the next EDA stage."])}))

(defn kami-render-ir
  "EDA render-IR compatible with the plain-data style of kami.render/frame."
  [project]
  (let [score (stage-score project)
        ips (vec (:eda.project/ip project))]
    {:frame/n (:eda.project/stage project)
     :frame/clear [0.97 0.98 0.99 1.0]
     :frame/kami-engine :render-ir-compatible
     :eda/project (:eda.project/id project)
     :eda/process (:eda.project/process project)
     :eda/stage (:stage/id (current-stage project))
     :eda/signoff (* 100 (:eda.score/signoff score))
     :eda/yield (:eda.score/yield score)
     :eda/co-sientist (select-keys (co-sientist-review project)
                                   [:eda.review/scores :eda.review/findings])
     :eda/maturity (select-keys (maturity-assessment project)
                                [:eda.maturity/level
                                 :eda.maturity/readiness-score
                                 :eda.maturity/simulation-coverage
                                 :eda.maturity/useable-for])
     :frame/passes
     [{:pass/id :eda-main
       :pass/target :canvas
       :pass/draws
       (vec
        (map-indexed
         (fn [i ip]
           {:draw/pipeline :eda-layer-rect
            :draw/mesh :rect
            :draw/material (nth [:M1 :M4 :Mtop] (mod i 3))
            :draw/instances {:count 1
                             :rect [(+ 90 (* (mod i 3) 210))
                                    (+ 90 (* (quot i 3) 140))
                                    (+ 140 (if (= ip :ml) 70 0))
                                    (+ 80 (if (= ip :sram) 45 0))]
                             :tint (nth ["#2563eb" "#16825d" "#c2410c" "#0891b2" "#6d28d9" "#b45309"] (mod i 6))
                             :label (str "macro-" (name ip))}})
         ips))}]}))
