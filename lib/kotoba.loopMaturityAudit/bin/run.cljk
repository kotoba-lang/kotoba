(ns run
  (:require [loop-maturity-audit.core :as audit]))

(let [root (or (System/getenv "GFTD_ROOT") "/Users/junkawasaki/github/com-junkawasaki")
      r (audit/run-cycle! {:root root})]
  (println "== loop-maturity-audit ==")
  (println "status:" (:status (:audit r)))
  (println "computed-at:" (:computed-at (:audit r)) "age-days:" (:age-days (:audit r)))
  (println "west projects:" (:west-projects (:audit r))
           "/ maturity entities:" (:maturity-entities (:audit r))
           "/ missing:" (:missing (:audit r)))
  (println (:proposal r))
  (println "evidence ledger:" (:ledger-path r)))
