(ns run
  (:require [clojure.test :as t]
            [kotoba.ontology-viz.catalog-test]
            [kotoba.ontology-viz.graph-test]
            [kotoba.ontology-viz.render-test]
            [kotoba.ontology-viz.security-test]
            [kotoba.ontology-viz.yataverse-test]))

(defmethod t/report #?(:clj :summary :cljs [:cljs.test/default :summary]) [m]
  (println "ONTOLOGY-VIZ ASSERTIONS"
           (+ (:pass m 0) (:fail m 0) (:error m 0))
           "pass" (:pass m 0)
           "fail" (:fail m 0)
           "error" (:error m 0))
  (flush)
  (when (pos? (+ (:fail m 0) (:error m 0)))
    #?(:clj (System/exit 1)
       :cljs (when (exists? js/process) (.exit js/process 1)))))

(t/run-tests 'kotoba.ontology-viz.catalog-test
             'kotoba.ontology-viz.graph-test
             'kotoba.ontology-viz.render-test
             'kotoba.ontology-viz.security-test
             'kotoba.ontology-viz.yataverse-test)
