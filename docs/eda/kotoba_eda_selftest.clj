(ns kotoba.eda.selftest
  "Asserts the CLJC-generated page still carries every id/class
  resources/eda_app.js depends on, and that the JS + CSS made it through
  unmodified. Not a cognitect-test-runner suite: kotoba_eda_ui.cljc /
  kotoba_eda_style.cljc are flat-file `load-file`d (see kotoba_eda_build.clj
  docstring for why — source.html serves them by flat filename), so they
  aren't on a normal classpath a namespace-discovering test runner can find.

  Run from this directory: clojure -M:test"
  (:require [clojure.test :refer [deftest is run-tests]]
            [clojure.string :as str]
            [kotoba.html :as html]))

(load-file "kotoba_eda_style.cljc")
(load-file "kotoba_eda_ui.cljc")

(def script (slurp "resources/eda_app.js"))
(def doc (html/html5 (kotoba.eda.ui/page script)))

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

(let [{:keys [fail error]} (run-tests 'kotoba.eda.selftest)]
  (when (or (pos? fail) (pos? error))
    (System/exit 1)))
