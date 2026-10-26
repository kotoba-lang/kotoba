(ns run (:require [cljs.test :as t] [kotoba-harness.search-test]))
(defmethod t/report [::t/default :end-run-tests] [m] (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))
(t/run-tests 'kotoba-harness.search-test)
