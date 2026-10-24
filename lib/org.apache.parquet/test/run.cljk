(ns run
  (:require [clojure.test :as t]
            [parquet.reader-test]
            [parquet.writer-test]))
(defmethod t/report [::t/default :end-run-tests] [m]
  (when-not (t/successful? m) (js/process.exit 1)))
(t/run-tests 'parquet.reader-test 'parquet.writer-test)
