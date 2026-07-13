(ns kotoba-eda-selftest
  "Asserts the CLJC-generated page still carries the contract the reagent
  app (kotoba_eda_app.cljs, compiled to resources/main.js) and the page's
  consumers depend on, and that the compiled bundle + design-system CSS made
  it through intact. Not a cognitect-test-runner suite: kotoba_eda_ui.cljc /
  kotoba_eda_style.cljc are flat single-segment namespaces (see
  kotoba_eda_build.clj docstring for why — source.html serves them by flat
  filename), which plain `require` resolves fine off this dir's `:paths
  [\".\"]` root.

  Run from this directory: clojure -M:test"
  (:require [clojure.test :refer [deftest is run-tests]]
            [clojure.string :as str]
            [kotoba-eda-style]
            [kotoba-eda-ui :as ui]))

(def script (slurp "resources/main.js"))
(def doc (ui/page-html script))

;; ids the cljs actually queries (mount point + canvas), the nav anchor
;; targets, and the SSR fallback's live-region ids the reagent views
;; re-create on mount.
(def contract-ids
  ["app" "eda-canvas" "flow" "manufacturing" "formats" "coverage"
   "title" "metric-stage" "metric-signoff" "metric-yield" "metric-cost"
   "target" "process" "die" "die-label" "volume" "volume-label"
   "ip-cpu" "ip-sram" "ip-analog" "ip-serdes" "ip-ml" "ip-otp"
   "artifact-files" "artifact-log" "runner-log" "murakumo-log"
   "runner-result-files" "signoff-evidence-files"
   "gates" "stages" "mfg-summary"
   "maturity-cards" "maturity-use" "sim-matrix" "readiness-log"
   "coverage-cards" "coverage-matrix" "signoff-evidence-matrix"
   "runner-result-log" "llm-log" "co-scores" "co-findings"
   "datom-log" "render-ir"])

;; every data-act the delegated dispatcher (kotoba_eda_app.cljs
;; act-handlers + view/gate prefixes) handles must be declared on the page.
(def contract-acts
  ["run-all" "advance" "inject" "export-json" "download-packet"
   "co-review" "maturity-audit" "runner-plan"
   "download-runner-plan" "murakumo-submit" "download-murakumo-payload"
   "load-sample-signoff" "download-signoff-template"
   "view/layout" "view/flow" "view/wafer" "view/package"])

(deftest every-contract-id-present
  (doseq [id contract-ids]
    (is (str/includes? doc (str "id=\"" id "\"")) (str "missing id=" id))))

(deftest every-contract-act-present
  (doseq [act contract-acts]
    (is (str/includes? doc (str "data-act=\"" act "\"")) (str "missing data-act=" act))))

(deftest design-system-css-present
  ;; the kotoba-ui theme bundle (HIG tokens light+dark, cascade layers) and
  ;; the unlayered app CSS both made it into the page.
  (doseq [marker ["@layer kotoba.hig, kotoba.glass"
                  "--hig-color-label" "--hig-color-tint" "--hig-palette-green"
                  ".workspace" ".canvas-tabs" ".stage-grid"]]
    (is (str/includes? doc marker) (str "missing CSS marker " marker))))

(deftest canvas-kami-engine-contract
  (is (str/includes? doc "data-kami-engine=\"render-ir\"")))

(deftest script-embedded-verbatim
  (is (str/includes? doc "window.__kotobaEda"))
  (is (str/includes? doc (str/trim script))))

(deftest doctype-and-lang
  (is (str/starts-with? doc "<!doctype html>"))
  (is (str/includes? doc "<html lang=\"ja\"")))

(defn -main [& _args]
  (let [{:keys [fail error]} (run-tests 'kotoba-eda-selftest)]
    (when (or (pos? fail) (pos? error))
      (System/exit 1))))
