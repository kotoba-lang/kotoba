(ns kotoba-eda-selftest
  "Asserts the CLJC-generated page still carries every id/class the reagent
  app (kotoba_eda_app.cljs, compiled to resources/main.js)
  depends on, and that the compiled bundle + CSS made it through intact.
  Not a cognitect-test-runner suite: kotoba_eda_ui.cljc / kotoba_eda_style.cljc
  are flat single-segment namespaces (see kotoba_eda_build.clj docstring for
  why — source.html serves them by flat filename), which plain `require`
  resolves fine off this dir's `:paths [\".\"]` root.

  Run from this directory: clojure -M:test"
  (:require [clojure.test :refer [deftest is run-tests]]
            [clojure.string :as str]
            [kotoba.html :as html]
            [kotoba-eda-style]
            [kotoba-eda-ui :as ui]))

(def script (slurp "resources/main.js"))
(def doc (html/html5 (ui/page script)))

;; every $("...") / getElementById target the JS actually uses
(def js-ids
  ["title" "metric-stage" "metric-signoff" "metric-yield" "metric-cost"
   "target" "process" "die" "die-label" "volume" "volume-label"
   "ip-cpu" "ip-sram" "ip-analog" "ip-serdes" "ip-ml" "ip-otp"
   "run-all" "advance" "inject" "export-json" "download-packet"
   "co-review" "maturity-audit" "runner-plan" "murakumo-submit"
   "artifact-files" "artifact-log" "runner-log" "murakumo-log"
   "runner-result-files" "signoff-evidence-files"
   "load-sample-signoff" "download-signoff-template"
   "download-runner-plan" "download-murakumo-payload"
   "gates" "eda-canvas" "stages" "manufacturing" "mfg-summary"
   "maturity-cards" "maturity-use" "sim-matrix" "readiness-log"
   "coverage-cards" "coverage-matrix" "signoff-evidence-matrix"
   "runner-result-log" "llm-log" "co-scores" "co-findings"
   "datom-log" "render-ir"])

(deftest every-js-id-present
  (doseq [id js-ids]
    (is (str/includes? doc (str "id=\"" id "\"")) (str "missing id=" id))))

(deftest css-custom-properties-present
  (doseq [var-name ["--bg" "--panel" "--ink" "--muted" "--line" "--blue"
                     "--cyan" "--green" "--amber" "--red" "--violet"
                     "--mono" "--sans"]]
    (is (str/includes? doc var-name) (str "missing CSS var " var-name))))

(deftest script-embedded-verbatim
  (is (str/includes? doc "window.__kotobaEda"))
  (is (str/includes? doc (str/trim script))))

(deftest doctype-and-lang
  (is (str/starts-with? doc "<!DOCTYPE html>"))
  (is (str/includes? doc "<html lang=\"ja\">")))

(defn -main [& _args]
  (let [{:keys [fail error]} (run-tests 'kotoba-eda-selftest)]
    (when (or (pos? fail) (pos? error))
      (System/exit 1))))
