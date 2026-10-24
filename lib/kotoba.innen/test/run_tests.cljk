(ns run-tests
  (:require [cljs.test :as t]
            [innen.algo-test]
            [innen.core-test]
            [innen.schema-test]
            [innen.time-test]
            [innen.tx-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (when-not (t/successful? m)
    (js/process.exit 1)))

(t/run-tests 'innen.time-test 'innen.schema-test 'innen.core-test 'innen.algo-test 'innen.tx-test)
