(ns run
  (:require [clojure.test :as t]
            [dango.shape-test] [dango.caveat-test] [dango.chain-test] [dango.vectors-test]))
(defmethod t/report #?(:clj :summary :cljs [:cljs.test/default :summary]) [m]
  (println "ASSERTIONS" (+ (:pass m 0) (:fail m 0) (:error m 0)) "fail" (:fail m 0) "error" (:error m 0)))
(t/run-tests 'dango.shape-test 'dango.caveat-test 'dango.chain-test 'dango.vectors-test)
