(ns kotoba.eda.ui
  "Hiccup + shadow-css style source for the kotoba EDA workbench.

  The GitHub Pages page is static HTML today, but this namespace is the canonical
  data-driven UI shape for the CLJS build path: components return Hiccup vectors
  and styles are plain data in the same spirit as shadow-css."
  (:require [clojure.string :as str]))

(def tokens
  {:color/bg "#f7f8fb"
   :color/panel "#ffffff"
   :color/ink "#172033"
   :color/muted "#667085"
   :color/line "#d7dce5"
   :color/blue "#2563eb"
   :radius/card "8px"
   :font/sans "system-ui, -apple-system, Hiragino Kaku Gothic ProN, Noto Sans JP, sans-serif"
   :font/mono "SFMono-Regular, ui-monospace, Menlo, Consolas, monospace"})

(def shadow-css
  {:eda/panel
   {:background "var(--panel)"
    :border "1px solid var(--line)"
    :border-radius "8px"
    :padding "14px"}
   :eda/button
   {:min-height "34px"
    :border "1px solid var(--line)"
    :border-radius "6px"
    :background "#fff"
    :color "var(--ink)"
    :font-weight 690
    :cursor "pointer"
    :padding "7px 10px"}
   :eda/log-row
   {:background "var(--panel)"
    :border "1px solid var(--line)"
    :border-radius "8px"
    :padding "8px"
    :font-size "12px"}
   :eda/maturity-grid
   {:display "grid"
    :grid-template-columns "repeat(3, minmax(0, 1fr))"
    :gap "8px"
    :margin "10px 0"}
   :eda/source-pre
   {:overflow "auto"
    :min-height "60vh"
    :background "#101827"
    :color "#dbeafe"
    :font "12px/1.55 var(--mono)"}})

(defn badge
  [label status]
  [:span.badge {:class (name status)} label])

(defn action-button
  [{:keys [id label primary? wide? danger?]}]
  [:button (cond-> {:id id}
             primary? (update :class str " primary")
             wide? (update :class str " wide")
             danger? (update :class str " danger"))
   label])

(defn artifact-intake-panel
  []
  [:div.panel
   [:h2 "Artifact Intake"]
   [:div.drop
    [:label "Upload EDA files"
     [:input#artifact-files
      {:type "file"
       :multiple true
       :accept ".v,.sv,.svh,.vhd,.vhdl,.sp,.spi,.cir,.ckt,.cdl,.sdc,.upf,.lib,.lef,.def,.gds,.gdsii,.oas,.oasis,.vcd,.fst,.sdf,.saif,.stil,.wgl,.rpt,.log,.drc,.lvs,.rule,.rules,.deck"}]]]
   [:div#artifact-log.log {:style {:margin-top "10px" :max-height "240px"}}]])

(defn runner-adapter-panel
  []
  [:div.panel
   [:h2 "Runner Adapter"]
   [:p "ブラウザは EDN job plan を作るだけです。実行は host/murakumo runner が policy gate 後に行います。"]
   [:div.actions
    (action-button {:id "download-runner-plan" :label "Download runner plan" :wide? true})
    (action-button {:id "murakumo-submit" :label "Build murakumo payload" :wide? true})
    (action-button {:id "download-murakumo-payload" :label "Download murakumo payload" :wide? true})]
   [:div#runner-log.log {:style {:margin-top "10px" :max-height "260px"}}]
   [:div#murakumo-log.log {:style {:margin-top "10px" :max-height "180px"}}]
   [:div.source-links
    [:a {:href "source.html?file=eda_runner_adapters.edn"} "Runner adapters EDN"]
    [:a {:href "source.html?file=kotoba_eda_runner.cljc"} "Runner CLJC"]
    [:a {:href "source.html?file=eda_murakumo_job.edn"} "Murakumo job EDN"]
    [:a {:href "source.html?file=kotoba_eda_murakumo.cljc"} "Murakumo CLJC"]
    [:a {:href "source.html?file=runner_host.clj"} "Host runner"]]])

(defn manufacturing-readiness-panel
  []
  [:div#manufacturing.panel
   [:h2 "Manufacturing Readiness"]
   [:p#mfg-summary "Run the flow to create GDS/OASIS, rule reports, waiver manifest, mask order plan, wafer traveller, probe plan, package BoM, ATE vectors and QA release packet."]
   [:div#maturity-cards.maturity-grid]
   [:div#maturity-use]
   [:table.matrix {:aria-label "Simulation matrix"}
    [:thead [:tr [:th "Simulation"] [:th "Tool"] [:th "Status"] [:th "Coverage"]]]
    [:tbody#sim-matrix]]
   [:div#readiness-log.log {:style {:margin-top "10px" :max-height "260px"}}]])

(defn run-control-panel
  []
  [:div.panel
   [:h2 "Run Control"]
   [:div.actions
    (action-button {:id "run-all" :label "Run full flow" :primary? true :wide? true})
    (action-button {:id "advance" :label "Advance stage"})
    (action-button {:id "inject" :label "Inject issue" :danger? true})
    (action-button {:id "export-json" :label "Export datoms"})
    (action-button {:id "download-packet" :label "Manufacturing packet"})
    (action-button {:id "co-review" :label "Run co-sientist review" :wide? true})
    (action-button {:id "maturity-audit" :label "Run maturity audit" :wide? true})
    (action-button {:id "runner-plan" :label "Build runner plan" :wide? true})]])

(defn workbench-panels
  []
  [:<>
   (run-control-panel)
   (artifact-intake-panel)
   (runner-adapter-panel)
   (manufacturing-readiness-panel)])

