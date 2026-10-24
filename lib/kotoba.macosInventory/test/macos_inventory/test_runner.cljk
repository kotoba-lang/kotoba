(ns macos-inventory.test-runner
  (:require [cljs.test :as t]
            [macos-inventory.core-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(defn -main [& _] (t/run-tests 'macos-inventory.core-test))
