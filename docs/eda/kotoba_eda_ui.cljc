(ns kotoba-eda-ui
  "Hiccup source for the kotoba EDA Flow Workbench page (docs/eda/index.html),
  on the kotoba-lang design-system paved road (kotoba-ui/docs/agent-guide.md):
  requires only kotoba-ui.core + appkit.core (desktop/dense defaults), page
  chrome from shell scaffolds (app-shell/nav-bar/stack), dense panes from
  appkit/panel, controls/badges/tab-bar from kotoba-ui, typography via the
  HIG text styles, and every color from the ONE `theme` map / `--hig-*`
  tokens (kotoba-eda-style is the small unlayered app CSS).

  This is the initial/no-JS-fallback paint: `#app` is the reagent mount point
  (kotoba_eda_app.cljs) — on load `init!` replaces its content with the fully
  reactive render bound to a single ratom, restoring `id=\"eda-canvas\"` +
  `data-kami-engine=\"render-ir\"` on the canvas it (re)creates so the
  kami-engine contract survives the remount. Interactive elements carry
  `data-act` (the shitsuke portable-interaction contract); the reagent app
  dispatches them via one delegated click handler. Keep the structure (ids,
  classes, data-act values) in sync with kotoba_eda_app.cljs's views."
  (:require [kotoba-ui.core :as ui]
            [appkit.core :as appkit]
            [kotoba-eda-style :as style]))

(def theme
  "The one theme map (agent-guide rule 5) — the only place a hex color is
  legitimate in app code. Accent = the workbench's pre-migration brand blue
  (the old --blue custom prop); :accent-dark a lighter same-hue blue for
  dark-appearance legibility; :auto follows the OS."
  {:accent "#2563eb" :accent-dark "#60A5FA" :appearance :auto})

(defn panel
  "appkit desktop pane (thick surface, flat elevation) whose body is the
  child list — the workbench's dense-pane unit."
  [opts & children]
  (appkit/panel (apply list children) opts))

(defn nav []
  (ui/nav-bar "kotoba / eda"
              {:trailing
               [:nav.nav-links {:aria-label "Workbench links"}
                [:a {:href "../"} "kotoba"]
                [:a {:href "#flow"} "Flow"]
                [:a {:href "#manufacturing"} "Manufacturing"]
                [:a {:href "#formats"} "Formats"]
                [:a {:href "source.html?file=kotoba_eda_core.cljc"} "CLJC"]
                [:a {:href "source.html?file=kotoba_eda_formats.cljc"} "Formats CLJC"]
                [:a {:href "source.html?file=kami_render_ir.edn"} "kami IR"]
                [:a {:href "../ADR-kotoba-eda-web-semiconductor-app.md"} "ADR"]
                [:a {:href "https://github.com/kotoba-lang/kotoba"} "GitHub"]]}))

(defn hero []
  [:section.hero {:aria-labelledby "title"}
   (panel {}
     [:h1#title.hig-title1 "kotoba EDA Flow Workbench"]
     [:p.panel-note "ブラウザ内で半導体の要求、設計、検証、サインオフ、製造引き渡しまでを一つの流れとして操作する実験版です。正本は "
      [:code ".cljc"] " の純粋データモデルで、描画面は kami-engine の render-IR 形状に寄せています。"]
     [:div.badges
      (ui/badge "CLJC workflow model" {:class "ok"})
      (ui/badge "kami render-IR" {:class "ok"})
      (ui/badge "LLM proposals only" {:class "warn"})
      (ui/badge "Foundry upload requires gate" {:class "stop"})])
   (panel {}
     [:h2.panel-title.hig-headline "Current Run"]
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
      [:a {:href "../ADR-kotoba-eda-web-semiconductor-app.edn"} "ADR EDN"]])])

(defn project-panel []
  (panel {}
    [:h2.panel-title.hig-headline "Project"]
    [:label.field "Target product"
     (ui/menu-select [["sensor-asic" "Sensor ASIC"]
                      ["edge-accelerator" "Edge AI Accelerator"]
                      ["pmic" "PMIC / BCD"]
                      ["mixed-signal" "Mixed-signal Controller"]]
                     {:id "target" :value "sensor-asic"})]
    [:label.field "Process / PDK"
     (ui/menu-select [["sky130" "Sky130-like open PDK"]
                      ["gf180" "GF180-like mixed signal"]
                      ["bcd180" "180nm BCD"]
                      ["cmos28" "28nm CMOS"]]
                     {:id "process" :value "sky130"})]
    [:label.field "Die size " [:span#die-label "16 mm²"]
     (ui/slider {:id "die" :min 4 :max 144 :value 16})]
    [:label.field "Volume " [:span#volume-label "25k units"]
     (ui/slider {:id "volume" :min 1 :max 1000 :value 25})]
    [:div.checks {:aria-label "IP blocks"}
     (ui/checkbox " RISC-V" {:id "ip-cpu" :checked true})
     (ui/checkbox " SRAM" {:id "ip-sram" :checked true})
     (ui/checkbox " Analog macro" {:id "ip-analog"})
     (ui/checkbox " SERDES" {:id "ip-serdes"})
     (ui/checkbox " ML array" {:id "ip-ml"})
     (ui/checkbox " OTP" {:id "ip-otp" :checked true})]))

(defn run-control-panel []
  (panel {}
    [:h2.panel-title.hig-headline "Run Control"]
    [:div.actions
     (ui/button "Run full flow" {:act "run-all" :class "primary wide"})
     (ui/button "Advance stage" {:act "advance"})
     (ui/button "Inject issue" {:act "inject" :class "danger"})
     (ui/button "Export datoms" {:act "export-json"})
     (ui/button "Manufacturing packet" {:act "download-packet"})
     (ui/button "Run co-sientist review" {:act "co-review" :class "wide"})
     (ui/button "Run maturity audit" {:act "maturity-audit" :class "wide"})
     (ui/button "Build runner plan" {:act "runner-plan" :class "wide"})]))

(defn artifact-intake-panel []
  (panel {}
    [:h2.panel-title.hig-headline "Artifact Intake"]
    [:div.drop
     [:label.field "Upload EDA files"
      [:input#artifact-files
       {:type "file" :multiple true
        :accept ".v,.sv,.svh,.vhd,.vhdl,.sp,.spi,.cir,.ckt,.cdl,.sdc,.upf,.lib,.lef,.def,.gds,.gdsii,.oas,.oasis,.vcd,.fst,.sdf,.saif,.stil,.wgl,.rpt,.log,.drc,.lvs,.rule,.rules,.deck"}]]]
    [:div#artifact-log.log {:style {:margin-top "10px" :max-height "240px"}}]))

(defn runner-adapter-panel []
  (panel {}
    [:h2.panel-title.hig-headline "Runner Adapter"]
    [:p.panel-note "ブラウザは EDN job plan を作るだけです。実行は host/murakumo runner が policy gate 後に行います。"]
    [:div.actions
     (ui/button "Download runner EDN" {:act "download-runner-plan" :class "wide"})
     (ui/button "Build murakumo payload" {:act "murakumo-submit" :class "wide"})
     (ui/button "Download murakumo EDN" {:act "download-murakumo-payload" :class "wide"})]
    [:div#runner-log.log {:style {:margin-top "10px" :max-height "260px"}}]
    [:div#murakumo-log.log {:style {:margin-top "10px" :max-height "180px"}}]
    [:div.drop {:style {:margin-top "10px"}}
     [:label.field "Import runner result JSON"
      [:input#runner-result-files {:type "file" :multiple true :accept ".json"}]]]
    [:div.drop {:style {:margin-top "10px"}}
     [:label.field "Import signoff evidence JSON"
      [:input#signoff-evidence-files {:type "file" :multiple true :accept ".json"}]]
     [:div.actions {:style {:margin-top "8px"}}
      (ui/button "Load sample signoff evidence" {:act "load-sample-signoff" :class "wide"})
      (ui/button "Download evidence template" {:act "download-signoff-template" :class "wide"})]]
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
     [:a {:href "source.html?file=runner_host.clj"} "Host runner"]]))

(defn policy-gates-panel []
  (panel {}
    [:h2.panel-title.hig-headline "Policy Gates"]
    [:div#gates]))

(defn viewer-panel []
  (panel {}
    [:h2.panel-title.hig-headline "kami-engine Viewer"]
    [:div.canvas-wrap
     (ui/tab-bar [["view/layout" "Layout"]
                  ["view/flow" "Flow"]
                  ["view/wafer" "Wafer"]
                  ["view/package" "Package"]]
                 "view/layout"
                 {:class "canvas-tabs"})
     [:canvas#eda-canvas {:width "1080" :height "630" :data-kami-engine "render-ir"}]]))

(defn stages-panel []
  (panel {}
    [:h2.panel-title.hig-headline "Design → Manufacturing Stages"]
    [:div#stages.stage-grid]))

(defn manufacturing-readiness-panel []
  (panel {:id "manufacturing"}
    [:h2.panel-title.hig-headline "Manufacturing Readiness"]
    [:p#mfg-summary.panel-note "Run the flow to create GDS/OASIS, rule reports, waiver manifest, mask order plan, wafer traveller, probe plan, package BoM, ATE vectors and QA release packet."]
    [:div#maturity-cards.maturity-grid]
    [:div#maturity-use]
    [:table.matrix {:aria-label "Simulation matrix"}
     [:thead [:tr [:th "Simulation"] [:th "Tool"] [:th "Status"] [:th "Coverage"]]]
     [:tbody#sim-matrix]]
    [:div#readiness-log.log {:style {:margin-top "10px" :max-height "260px"}}]))

(defn coverage-panel []
  (panel {:id "coverage"}
    [:h2.panel-title.hig-headline "Coverage"]
    [:p.panel-note "Runner results, uploaded reports, and stage-model fallback are separated as "
     [:code ":eda.coverage/*"] " data."]
    [:div#coverage-cards.maturity-grid]
    [:table.matrix {:aria-label "Coverage matrix"}
     [:thead [:tr [:th "Metric"] [:th "Source"] [:th "Status"] [:th "Score"]]]
     [:tbody#coverage-matrix]]
    [:h3.hig-subheadline "Signoff Evidence Gates"]
    [:table.matrix {:aria-label "Signoff evidence matrix"}
     [:thead [:tr [:th "Gate"] [:th "Tool"] [:th "Status"] [:th "Evidence"]]]
     [:tbody#signoff-evidence-matrix]]
    [:div#runner-result-log.log {:style {:margin-top "10px" :max-height "220px"}}]
    [:div.source-links
     [:a {:href "source.html?file=eda_coverage_schema.edn"} "Coverage schema EDN"]
     [:a {:href "source.html?file=eda_signoff_evidence.edn"} "Signoff evidence EDN"]]))

(defn formats-panel []
  (panel {:id "formats"}
    [:h2.panel-title.hig-headline "File Format Registry"]
    [:p.panel-note "EDA artifacts are CID-addressed files with EDN manifests. Each format maps to software adapters, operations, policy gates and EDN-centered converter pipelines."]
    [:div.badges
     (ui/badge ".v .sv .vhd" {:class "ok"})
     (ui/badge ".sp .cdl .sdc .upf" {:class "ok"})
     (ui/badge ".lib .lef .def" {:class "ok"})
     (ui/badge ".gds .oas" {:class "warn"})
     (ui/badge ".vcd .fst .sdf .saif" {:class "warn"})
     (ui/badge ".stil .wgl .deck" {:class "stop"})]
    [:div.log {:style {:margin-top "10px" :max-height "210px"}}
     [:div.log-row [:b "RTL"] [:small ".v/.sv/.vhd -> EDN RTL graph -> Yosys/Surelog/slang/GHDL -> synth/sim/formal"]]
     [:div.log-row [:b "Analog"] [:small ".sp/.cdl -> EDN netlist -> ngspice/Xyce/Netgen -> sim/LVS"]]
     [:div.log-row [:b "Physical"] [:small ".lib/.lef/.def/.gds/.oas -> EDN physical model -> OpenROAD/KLayout/Magic/OpenSTA -> P&R/signoff/tapeout"]]
     [:div.log-row [:b "Analysis"] [:small ".vcd/.fst/.sdf/.saif/.rpt -> EDN summaries/findings -> kami render-IR and LLM proposal input"]]
     [:div.log-row [:b "Manufacturing"] [:small ".stil/.wgl + GDS/OASIS + reports -> EDN release packet -> ATE/foundry handoff gates"]]]
    [:div.source-links
     [:a {:href "source.html?file=eda_file_formats.edn"} "Canonical EDN registry"]
     [:a {:href "source.html?file=kotoba_eda_formats.cljc"} "Pure CLJC query layer"]]))

(defn proposal-panel []
  (panel {} [:h2.panel-title.hig-headline "LLM / murakumo Proposals"] [:div#llm-log.log]))

(defn co-sientist-panel []
  (panel {}
    [:h2.panel-title.hig-headline "Co-sientist Quality"]
    [:div#co-scores.score-list]
    [:div#co-findings.log {:style {:margin-top "10px" :max-height "220px"}}]))

(defn datom-panel []
  (panel {} [:h2.panel-title.hig-headline "Datom Log"] [:div#datom-log.log]))

(defn render-ir-panel []
  (panel {} [:h2.panel-title.hig-headline "render-IR"] [:pre#render-ir]))

(defn workspace []
  [:section#flow.workspace
   (ui/stack {:gap :3}
     (project-panel)
     (run-control-panel)
     (artifact-intake-panel)
     (runner-adapter-panel)
     (policy-gates-panel))
   (ui/stack {:gap :3}
     (viewer-panel)
     (stages-panel)
     (manufacturing-readiness-panel)
     (coverage-panel)
     (formats-panel))
   (ui/stack {:gap :3 :class "col-right"}
     (proposal-panel)
     (co-sientist-panel)
     (datom-panel)
     (render-ir-panel))])

(defn page-html
  "Full document string for docs/eda/index.html via kotoba-ui.core/->page
  (doctype + theme CSS + app CSS + shell page). `script-text` is the compiled
  reagent app bundle (resources/main.js, built by `npx shadow-cljs release
  app` from kotoba_eda_app.cljs), embedded verbatim as a raw <script> block.
  #app is the reagent mount point — see the ns docstring."
  [script-text]
  (ui/->page {:title "kotoba EDA Flow Workbench"
              :description "kotoba-lang EDA: CLJC workflow model with kami-engine render-IR for web semiconductor design-to-manufacturing flow."
              :lang "ja"
              :theme theme
              :head [:style [:hiccup/raw (style/page-css)]]}
             (ui/app-shell {:nav (nav)}
               [:div#app (hero) (workspace)])
             [:script [:hiccup/raw script-text]]))
