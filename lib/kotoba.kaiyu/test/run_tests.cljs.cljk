(ns run-tests
  (:require [cljs.test :as t]
            [kaiyu.core-test]
            [kaiyu.diagnose-test]
            [kaiyu.session-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (when-not (t/successful? m)
    (js/process.exit 1)))

(t/run-tests 'kaiyu.core-test 'kaiyu.diagnose-test 'kaiyu.session-test)
