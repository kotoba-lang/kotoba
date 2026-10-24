(ns run
  (:require [clojure.test :as t] [csv.core-test]))
(defmethod t/report [::t/default :end-run-tests] [m]
  (when-not (t/successful? m) (js/process.exit 1)))
(t/run-tests 'csv.core-test)
