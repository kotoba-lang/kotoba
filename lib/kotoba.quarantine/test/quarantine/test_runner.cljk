(ns quarantine.test-runner
  (:require [cljs.test :as t]
            [quarantine.core-test]
            [quarantine.host-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(defn -main [& _]
  (t/run-tests 'quarantine.core-test 'quarantine.host-test))
