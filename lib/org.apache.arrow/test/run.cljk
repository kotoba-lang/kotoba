(ns run
  (:require [clojure.test :as t]
            [arrow.reader-test]
            [arrow.writer-test]
            [arrow.group-test]))
(defmethod t/report [::t/default :end-run-tests] [m]
  (when-not (t/successful? m) (js/process.exit 1)))
(t/run-tests 'arrow.reader-test 'arrow.writer-test 'arrow.group-test)
