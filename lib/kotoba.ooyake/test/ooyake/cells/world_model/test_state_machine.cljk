(ns ooyake.cells.world-model.test-state-machine
  "Tests for ooyake WorldModelCell — cross-actor world-model reconcile
   (ADR-2606021600 §3, depends ADR-2606011000 + ADR-2606011800).
   1:1 port of test_world_model_cell.py (pytest → clojure.test)."
  (:require [clojure.test :refer [deftest is testing]]
            [ooyake.cells.world-model.state-machine :as sm]))

(def _GOV
  {"gov.jpn" {":gov.unit/id" "gov.jpn" ":gov.unit/level" ":country" ":gov.unit/name-en" "Japan"}
   "gov.jpn.meti" {":gov.unit/id" "gov.jpn.meti" ":gov.unit/level" ":ministry"
                   ":gov.unit/name-en" "METI" ":gov.unit/organism" "org.state.jp.meti"}
   "gov.jpn.mof" {":gov.unit/id" "gov.jpn.mof" ":gov.unit/level" ":ministry" ":gov.unit/name-en" "MOF"}
   "gov.xx.bad" {":gov.unit/id" "gov.xx.bad" ":gov.unit/level" ":agency"
                 ":gov.unit/name-en" "Bad" ":gov.unit/organism" "org.state.xx.missing"}
   "gov.jpn.city.13104" {":gov.unit/id" "gov.jpn.city.13104" ":gov.unit/level" ":ward"
                         ":gov.unit/name-en" "Shinjuku City"}
   "madoguchi.x" {":gov.unit/id" "madoguchi.x" ":gov.unit/level" ":madoguchi"}})

(def _ORGS
  {"org.state.jp.meti" {":organism/id" "org.state.jp.meti" ":organism/subkind" ":agency" ":organism/label" "METI"}
   "org.corp.tw.tsmc" {":organism/id" "org.corp.tw.tsmc" ":organism/subkind" ":corp" ":organism/label" "TSMC"}
   "org.state.us.orphan" {":organism/id" "org.state.us.orphan" ":organism/subkind" ":state" ":organism/label" "Orphan"}})

(deftest test-derive-organism-id
  (is (= "org.gov.jpn.meti" (sm/derive-organism-id "gov.jpn.meti")))
  (is (= "org.gov.usa" (sm/derive-organism-id "gov.usa")))
  (is (= "org.gov.weird" (sm/derive-organism-id "weird"))))

(deftest test-confirmed-dangling-proposed-and-exclusion
  (let [r (sm/reconcile-world-model _GOV _ORGS nil)]
    (is (= [{"unit" "gov.jpn.meti" "organism" "org.state.jp.meti"}]
           (get r "confirmed_links")))
    (is (= [{"unit" "gov.xx.bad" "organism" "org.state.xx.missing"}]
           (get r "dangling_links")))
    (let [proposed-units (sort (map #(get % "unit") (get r "proposed_links" [])))]
      (is (= ["gov.jpn" "gov.jpn.mof"] proposed-units)))
    (is (= 2 (get r "excluded_non_power_units")))
    (is (= 4 (get r "power_bearing_units")))))

(deftest test-orphan-and-non-gov-classification
  (let [r (sm/reconcile-world-model _GOV _ORGS nil)]
    (is (= ["org.state.us.orphan"]
           (sort (map #(get % "organism") (get r "orphan_gov_organisms" [])))))
    (is (= 1 (get r "non_gov_organisms_out_of_atlas")))))

(deftest test-coverage-pct
  (let [r (sm/reconcile-world-model _GOV _ORGS nil)]
    (is (= 1 (get-in r ["coverage" "reconciled"])))
    (is (= 25.0 (get-in r ["coverage" "reconciled_pct"])))))

(deftest test-cell-live-mode-gated
  (is (thrown? Exception
               (sm/world-model-cell-solve {"mode" "live"})))
  (try
    (sm/world-model-cell-solve {"mode" "live"})
    (catch Exception e
      (is (and (or (.contains (str e) "G4")
                   (.contains (str e) "G7"))
               (.contains (str e) "not activated"))))))

(deftest test-cell-unknown-mode-rejected
  (is (thrown? Exception
               (sm/world-model-cell-solve {"mode" "bogus"})))
  (try
    (sm/world-model-cell-solve {"mode" "bogus"})
    (catch Exception e
      (is (.contains (str e) "unknown world_model mode")))))

(deftest test-cell-default-mode-bundled
  (let [out (sm/world-model-cell-solve {})]
    (is (= "ok" (get out "status")))
    (is (= "bundled" (get-in out ["report" "mode"])))))
