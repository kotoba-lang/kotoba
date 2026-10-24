(ns run
  (:require [clojure.test :as t]
            [iceberg.table-test]
            [iceberg.rest-test]))
(defmethod t/report [::t/default :end-run-tests] [m]
  (when-not (t/successful? m) (js/process.exit 1)))
(t/run-tests 'iceberg.table-test 'iceberg.rest-test)
