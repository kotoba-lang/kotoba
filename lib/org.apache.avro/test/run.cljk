(ns run
  (:require [clojure.test :as t]
            [avro.reader-test]
            [avro.writer-test]))
(defmethod t/report [::t/default :end-run-tests] [m]
  (when-not (t/successful? m) (js/process.exit 1)))
(t/run-tests 'avro.reader-test 'avro.writer-test)
