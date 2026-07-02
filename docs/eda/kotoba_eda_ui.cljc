(ns kotoba.eda.ui
  "Hiccup source for the kotoba EDA Flow Workbench page (docs/eda/index.html).

  This is the canonical, data-driven shape of the deployed page: every id and
  class the page's JS (resources/eda_app.js) touches via getElementById /
  querySelector is declared here, once, as hiccup data — not hand-typed HTML
  strings. `page` assembles the full document (head/style via
  kotoba.eda.style + body markup below + the JS as a raw <script> block) and
  is rendered to docs/eda/index.html by build.clj via kotoba.html/html5.

  Kept in sync with the ids/classes resources/eda_app.js queries — grep that
  file for `$(\"...\")` / `querySelectorAll` before renaming or removing any
  id/class declared below."
  (:require [kotoba.eda.style :as style]))

(defn nav []
  [:nav
   [:div.nav-inner
    [:div.brand "kotoba / eda"]
    [:div.nav-links
     [:a {:href "../"} "kotoba"]
     [:a {:href "#flow"} "Flow"]
     [:a {:href "#manufacturing"} "Manufacturing"]
     [:a {:href "#formats"} "Formats"]
     [:a {:href "source.html?file=kotoba_eda_core.cljc"} "CLJC"]
     [:a {:href "source.html?file=kotoba_eda_formats.cljc"} "Formats CLJC"]
     [:a {:href "source.html?file=kami_render_ir.edn"} "kami IR"]
     [:a {:href "../ADR-kotoba-eda-web-semiconductor-app.md"} "ADR"]
     [:a {:href "https://github.com/kotoba-lang/kotoba"} "GitHub"]]]])

(defn hero []
  [:section.hero {:aria-labelledby "title"}
   [:div.panel
    [:h1#title "kotoba EDA Flow Workbench"]
    [:p "ブラウザ内で半導体の要求、設計、検証、サインオフ、製造引き渡しまでを一つの流れとして操作する実験版です。正本は "
     [:code ".cljc"] " の純粋データモデルで、描画面は kami-engine の render-IR 形状に寄せています。"]
    [:div.badges
     [:span.badge.ok "CLJC workflow model"]
     [:span.badge.ok "kami render-IR"]
     [:span.badge.warn "LLM proposals only"]
     [:span.badge.stop "Foundry upload requires gate"]]]
   [:div.panel
    [:h2 "Current Run"]
    [:div.metrics
     [:div.metric [:span "Stage"] [:b#metric-stage "Spec"]]
     [:div.metric [:span "Signoff"] [:b#metric-signoff "0%"]]
     [:div.metric [:span "Yield"] [:b#metric-yield "91.0%"]]
     [:div.metric [:span "Cost"] [:b#metric-cost "$0k"]]]
    [:div.source-links
     [:a {:href "source.html?file=kotoba_eda_core.cljc"} "CLJC model"]
     [:a {:href "source.html?file=eda_file_formats.edn"} "EDA formats EDN"]
     [:a {:href "source.html?file=kotoba_eda_formats.cljc"} "formats CLJC"]
     [:a {:href "source.html?file=kami_render_ir.edn"} "render-IR sample"]
     [:a {:href "../ADR-kotoba-eda-web-semiconductor-app.edn"} "ADR EDN"]]]])

(defn project-panel []
  [:div.panel
   [:h2 "Project"]
   [:label "Target product"
    [:select#target
     [:option {:value "sensor-asic"} "Sensor ASIC"]
     [:option {:value "edge-accelerator"} "Edge AI Accelerator"]
     [:option {:value "pmic"} "PMIC / BCD"]
     [:option {:value "mixed-signal"} "Mixed-signal Controller"]]]
   [:label "Process / PDK"
    [:select#process
     [:option {:value "sky130"} "Sky130-like open PDK"]
     [:option {:value "gf180"} "GF180-like mixed signal"]
     [:option {:value "bcd180"} "180nm BCD"]
     [:option {:value "cmos28"} "28nm CMOS"]]]
   [:label "Die size " [:span#die-label "16 mm²"]
    [:input#die {:type "range" :min "4" :max "144" :value "16"}]]
   [:label "Volume " [:span#volume-label "25k units"]
    [:input#volume {:type "range" :min "1" :max "1000" :value "25"}]]
   [:div.checks {:aria-label "IP blocks"}
    [:label [:input#ip-cpu {:type "checkbox" :checked true}] " RISC-V"]
    [:label [:input#ip-sram {:type "checkbox" :checked true}] " SRAM"]
    [:label [:input#ip-analog {:type "checkbox"}] " Analog macro"]
    [:label [:input#ip-serdes {:type "checkbox"}] " SERDES"]
    [:label [:input#ip-ml {:type "checkbox"}] " ML array"]
    [:label [:input#ip-otp {:type "checkbox" :checked true}] " OTP"]]])

(defn run-control-panel []
  [:div.panel
   [:h2 "Run Control"]
   [:div.actions
    [:button.primary.wide#run-all "Run full flow"]
    [:button#advance "Advance stage"]
    [:button.danger#inject "Inject issue"]
    [:button#export-json "Export datoms"]
    [:button#download-packet "Manufacturing packet"]
    [:button.wide#co-review "Run co-sientist review"]
    [:button.wide#maturity-audit "Run maturity audit"]
    [:button.wide#runner-plan "Build runner plan"]]])

(defn artifact-intake-panel []
  [:div.panel
   [:h2 "Artifact Intake"]
   [:div.drop
    [:label "Upload EDA files"
     [:input#artifact-files
      {:type "file" :multiple true
       :accept ".v,.sv,.svh,.vhd,.vhdl,.sp,.spi,.cir,.ckt,.cdl,.sdc,.upf,.lib,.lef,.def,.gds,.gdsii,.oas,.oasis,.vcd,.fst,.sdf,.saif,.stil,.wgl,.rpt,.log,.drc,.lvs,.rule,.rules,.deck"}]]]
   [:div#artifact-log.log {:style {:margin-top "10px" :max-height "240px"}}]])

(defn runner-adapter-panel []
  [:div.panel
   [:h2 "Runner Adapter"]
   [:p "ブラウザは EDN job plan を作るだけです。実行は host/murakumo runner が policy gate 後に行います。"]
   [:div.actions
    [:button.wide#download-runner-plan "Download runner EDN"]
    [:button.wide#murakumo-submit "Build murakumo payload"]
    [:button.wide#download-murakumo-payload "Download murakumo EDN"]]
   [:div#runner-log.log {:style {:margin-top "10px" :max-height "260px"}}]
   [:div#murakumo-log.log {:style {:margin-top "10px" :max-height "180px"}}]
   [:div.drop {:style {:margin-top "10px"}}
    [:label "Import runner result JSON"
     [:input#runner-result-files {:type "file" :multiple true :accept ".json"}]]]
   [:div.drop {:style {:margin-top "10px"}}
    [:label "Import signoff evidence JSON"
     [:input#signoff-evidence-files {:type "file" :multiple true :accept ".json"}]]
    [:div.actions {:style {:margin-top "8px"}}
     [:button.wide#load-sample-signoff "Load sample signoff evidence"]
     [:button.wide#download-signoff-template "Download evidence template"]]]
   [:div.source-links
    [:a {:href "https://github.com/kotoba-lang/eda"} "Native CLJC engine repo"]
    [:a {:href "https://kotoba-lang.github.io/eda/sample_flow.edn"} "Native EDN sample flow"]
    [:a {:href "https://kotoba-lang.github.io/eda/oss_manifest.edn"} "OSS report manifest"]
    [:a {:href "source.html?file=eda_runner_adapters.edn"} "Runner adapters EDN"]
    [:a {:href "source.html?file=kotoba_eda_runner.cljc"} "Runner CLJC"]
    [:a {:href "source.html?file=eda_signoff_evidence.edn"} "Signoff evidence EDN"]
    [:a {:href "source.html?file=eda_murakumo_job.edn"} "Murakumo job EDN"]
    [:a {:href "source.html?file=kotoba_eda_murakumo.cljc"} "Murakumo CLJC"]
    [:a {:href "source.html?file=kotoba_eda_ui.cljc"} "UI Hiccup"]
    [:a {:href "source.html?file=runner_host.clj"} "Host runner"]]])

(defn policy-gates-panel []
  [:div.panel
   [:h2 "Policy Gates"]
   [:div#gates]])

(defn left-column []
  [:aside.stack
   (project-panel)
   (run-control-panel)
   (artifact-intake-panel)
   (runner-adapter-panel)
   (policy-gates-panel)])

(defn viewer-panel []
  [:div.panel
   [:h2 "kami-engine Viewer"]
   [:div.canvas-wrap
    [:div.canvas-tabs
     [:button.active {:data-view "layout"} "Layout"]
     [:button {:data-view "flow"} "Flow"]
     [:button {:data-view "wafer"} "Wafer"]
     [:button {:data-view "package"} "Package"]]
    [:canvas#eda-canvas {:width "1080" :height "630" :data-kami-engine "render-ir"}]]])

(defn stages-panel []
  [:div.panel
   [:h2 "Design → Manufacturing Stages"]
   [:div#stages.stage-grid]])

(defn manufacturing-readiness-panel []
  [:div#manufacturing.panel
   [:h2 "Manufacturing Readiness"]
   [:p#mfg-summary "Run the flow to create GDS/OASIS, rule reports, waiver manifest, mask order plan, wafer traveller, probe plan, package BoM, ATE vectors and QA release packet."]
   [:div#maturity-cards.maturity-grid]
   [:div#maturity-use]
   [:table.matrix {:aria-label "Simulation matrix"}
    [:thead [:tr [:th "Simulation"] [:th "Tool"] [:th "Status"] [:th "Coverage"]]]
    [:tbody#sim-matrix]]
   [:div#readiness-log.log {:style {:margin-top "10px" :max-height "260px"}}]])

(defn coverage-panel []
  [:div#coverage.panel
   [:h2 "Coverage"]
   [:p "Runner results, uploaded reports, and stage-model fallback are separated as "
    [:code ":eda.coverage/*"] " data."]
   [:div#coverage-cards.maturity-grid]
   [:table.matrix {:aria-label "Coverage matrix"}
    [:thead [:tr [:th "Metric"] [:th "Source"] [:th "Status"] [:th "Score"]]]
    [:tbody#coverage-matrix]]
   [:h3 "Signoff Evidence Gates"]
   [:table.matrix {:aria-label "Signoff evidence matrix"}
    [:thead [:tr [:th "Gate"] [:th "Tool"] [:th "Status"] [:th "Evidence"]]]
    [:tbody#signoff-evidence-matrix]]
   [:div#runner-result-log.log {:style {:margin-top "10px" :max-height "220px"}}]
   [:div.source-links
    [:a {:href "source.html?file=eda_coverage_schema.edn"} "Coverage schema EDN"]
    [:a {:href "source.html?file=eda_signoff_evidence.edn"} "Signoff evidence EDN"]]])

(defn formats-panel []
  [:div#formats.panel
   [:h2 "File Format Registry"]
   [:p "EDA artifacts are CID-addressed files with EDN manifests. Each format maps to software adapters, operations, policy gates and EDN-centered converter pipelines."]
   [:div.badges
    [:span.badge.ok ".v .sv .vhd"]
    [:span.badge.ok ".sp .cdl .sdc .upf"]
    [:span.badge.ok ".lib .lef .def"]
    [:span.badge.warn ".gds .oas"]
    [:span.badge.warn ".vcd .fst .sdf .saif"]
    [:span.badge.stop ".stil .wgl .deck"]]
   [:div.log {:style {:margin-top "10px" :max-height "210px"}}
    [:div.log-row [:b "RTL"] [:small ".v/.sv/.vhd -> EDN RTL graph -> Yosys/Surelog/slang/GHDL -> synth/sim/formal"]]
    [:div.log-row [:b "Analog"] [:small ".sp/.cdl -> EDN netlist -> ngspice/Xyce/Netgen -> sim/LVS"]]
    [:div.log-row [:b "Physical"] [:small ".lib/.lef/.def/.gds/.oas -> EDN physical model -> OpenROAD/KLayout/Magic/OpenSTA -> P&R/signoff/tapeout"]]
    [:div.log-row [:b "Analysis"] [:small ".vcd/.fst/.sdf/.saif/.rpt -> EDN summaries/findings -> kami render-IR and LLM proposal input"]]
    [:div.log-row [:b "Manufacturing"] [:small ".stil/.wgl + GDS/OASIS + reports -> EDN release packet -> ATE/foundry handoff gates"]]]
   [:div.source-links
    [:a {:href "source.html?file=eda_file_formats.edn"} "Canonical EDN registry"]
    [:a {:href "source.html?file=kotoba_eda_formats.cljc"} "Pure CLJC query layer"]]])

(defn middle-column []
  [:section.stack
   (viewer-panel)
   (stages-panel)
   (manufacturing-readiness-panel)
   (coverage-panel)
   (formats-panel)])

(defn proposal-panel [] [:div.panel [:h2 "LLM / murakumo Proposals"] [:div#llm-log.log]])
(defn co-sientist-panel []
  [:div.panel [:h2 "Co-sientist Quality"]
   [:div#co-scores.score-list] [:div#co-findings.log {:style {:margin-top "10px" :max-height "220px"}}]])
(defn datom-panel [] [:div.panel [:h2 "Datom Log"] [:div#datom-log.log]])
(defn render-ir-panel [] [:div.panel [:h2 "render-IR"] [:pre#render-ir]])

(defn right-column []
  [:aside.stack
   (proposal-panel)
   (co-sientist-panel)
   (datom-panel)
   (render-ir-panel)])

(defn workspace []
  [:section#flow.workspace
   (left-column)
   (middle-column)
   (right-column)])

(defn head [css-text]
  [:head
   [:meta {:charset "utf-8"}]
   [:meta {:name "viewport" :content "width=device-width, initial-scale=1"}]
   [:title "kotoba EDA Flow Workbench"]
   [:meta {:name "description"
           :content "kotoba-lang EDA: CLJC workflow model with kami-engine render-IR for web semiconductor design-to-manufacturing flow."}]
   [:style css-text]])

(defn body [script-text]
  [:body
   (nav)
   [:main (hero) (workspace)]
   [:script script-text]])

(defn page
  "Full document hiccup for docs/eda/index.html. `script-text` is the
  page's JS (resources/eda_app.js), embedded verbatim as a raw <script>
  block — see the ns docstring for why the JS itself is not rewritten here."
  [script-text]
  [:html {:lang "ja"}
   (head (style/page-css))
   (body script-text)])
