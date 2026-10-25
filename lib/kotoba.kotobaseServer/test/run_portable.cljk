;; The nbb entry the fleet gate runs (scripts/fleet-ci/gates.edn, :nbb-test).
;;
;; shadow-cljs discovers test namespaces by `:ns-regexp "-test$"`; nbb has no
;; discovery, so this list IS the coverage claim. The two drifted: shadow ran
;; 17 namespaces, this file named 14, and shadow stopped being the gate when
;; :nbb-test replaced :shadow-test. `admission-test`, `clause-cardinality-test`
;; and `rules-test` were therefore gated by nothing at all.
;;
;; Every `-test` namespace under test/ must appear BOTH in the :require above
;; and in the `run-tests` call below -- being required is not being run.
;; scripts/verify-cljs-runner-completeness.cljs (superproject) is the ratchet.
(ns kss-run2
  (:require [clojure.test :as t]
            [kotobase.server.admission-test]
            [kotobase.server.clause-cardinality-test]
            [kotobase.server.handler-test]
            [kotobase.server.runtime-test]
            [kotobase.server.trampoline-test]
            [kotobase.server.ipns-test]
            [kotobase.server.rules-test]
            [kotobase.server.storage-test]
            [kotobase.server.pattern-source-test]
            [kotobase.server.query-exec-test]
            [kotobase.server.materialized-test]
            [kotobase.server.shadow-test]
            [kotobase.server.cypher-test]
            [kotobase.server.cypher-ldbc-test]
            [kotobase.server.sparql-snapshot-test]
            [kotobase.server.security.biscuit-authority-test]
            [kotobase.server.security.credential-test]))
(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println "SUMMARY" (:test m) "tests" (:pass m) "pass" (:fail m) "fail" (:error m) "error")
  (set! (.-exitCode js/process) (if (t/successful? m) 0 1)))
(t/run-tests 'kotobase.server.admission-test
             'kotobase.server.clause-cardinality-test
             'kotobase.server.handler-test 'kotobase.server.runtime-test
             'kotobase.server.trampoline-test 'kotobase.server.ipns-test
             'kotobase.server.rules-test
             'kotobase.server.storage-test 'kotobase.server.pattern-source-test
             'kotobase.server.query-exec-test 'kotobase.server.materialized-test
             'kotobase.server.shadow-test 'kotobase.server.cypher-test
             'kotobase.server.cypher-ldbc-test 'kotobase.server.sparql-snapshot-test
             'kotobase.server.security.biscuit-authority-test
             'kotobase.server.security.credential-test)
