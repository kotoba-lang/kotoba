(ns run
  (:require [clojure.test :as t]
            [dango.shape-test] [dango.caveat-test] [dango.chain-test] [dango.vectors-test]
            [authority.revocation-test]))
(defmethod t/report #?(:clj :summary :cljs [:cljs.test/default :summary]) [m]
  (println "ASSERTIONS" (+ (:pass m 0) (:fail m 0) (:error m 0)) "fail" (:fail m 0) "error" (:error m 0))
  (flush)
  (when (pos? (+ (:fail m 0) (:error m 0)))
    #?(:clj (System/exit 1)
       :cljs (when (exists? js/process) (.exit js/process 1)))))
(t/run-tests 'dango.shape-test 'dango.caveat-test 'dango.chain-test 'dango.vectors-test
             'authority.revocation-test)
