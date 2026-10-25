(ns ooyake.cells.reconcile.test-state-machine
  "Tests for ooyake ReconcileCell (ADR-2606021600 §5).
   1:1 port of test_reconcile_cell.py (pytest → clojure.test)."
  (:require [clojure.test :refer [deftest is testing]]
            [ooyake.cells.reconcile.state-machine :as sm]))

(deftest test-bundled-promotes-expected-units
  (let [rep (sm/reconcile nil nil)]
    ;; full JP central + proof-of-model chain + breadth rows
    (is (= 28 (get rep "total_units")) (get rep "total_units"))
    ;; exactly the 8 units present in authority-reference.edn, all agreeing
    (is (= 8 (get-in rep ["coverage" "authoritative_after"])))
    (is (= ["gov.gbr.hmrc"
            "gov.jpn"
            "gov.jpn.cao"
            "gov.jpn.meti"
            "gov.jpn.mof"
            "gov.jpn.mofa"
            "gov.jpn.pref.13"
            "gov.usa.treasury"]
           (get rep "promoted_to_authoritative")))))

(deftest test-no-conflicts-and-honest-remainder
  (let [rep (sm/reconcile nil nil)]
    (is (= [] (get rep "conflicts_kept_unverified")))
    ;; everything without an authority record stays representative (G5)
    (is (= 20 (count (get rep "no_authority_record_kept_representative"))))
    (is (= 20 (get-in rep ["coverage" "representative_after"])))))

(deftest test-cell-bundled-mode-ok
  (let [out (sm/reconcile-cell-solve {"mode" "bundled"})]
    (is (= "ok" (get out "status")))
    (is (= 8 (get-in out ["report" "coverage" "authoritative_after"])))))

(deftest test-cell-live-mode-gated
  (is (thrown? Exception
               (sm/reconcile-cell-solve {"mode" "live"})))
  ;; Verify the exception message contains the gating info
  (try
    (sm/reconcile-cell-solve {"mode" "live"})
    (catch Exception e
      (is (and (.contains (str e) "G4")
               (.contains (str e) "not activated"))))))

(deftest test-cell-unknown-mode-rejected
  (is (thrown? Exception
               (sm/reconcile-cell-solve {"mode" "bogus"})))
  (try
    (sm/reconcile-cell-solve {"mode" "bogus"})
    (catch Exception e
      (is (.contains (str e) "unknown reconcile mode")))))

(deftest test-cell-default-mode-bundled
  (let [out (sm/reconcile-cell-solve {})]
    (is (= "ok" (get out "status")))
    (is (= "bundled" (get-in out ["report" "mode"])))))
