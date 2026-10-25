(ns run-tests
  (:require [cljs.test :as t]
            [kotoba.statement-fetch-test]
            [kotoba.connector-test]
            [kotoba.institutions-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (when-not (t/successful? m)
    (js/process.exit 1)))

(t/run-tests 'kotoba.statement-fetch-test
             'kotoba.connector-test
             'kotoba.institutions-test)
