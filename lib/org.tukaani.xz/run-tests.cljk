(ns run-tests
  "Runs the runtime-agnostic suite on ClojureScript via nbb (paths come from
   nbb.edn, including the sibling org-ietf-deflate checkout).

   The JVM suite adds conformance against liblzma and the xz CLI."
  (:require [cljs.test :as t]
            [xz.portable-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\nnbb: " (:test m) " tests, " (:pass m) " passed, "
                (:fail m) " failed, " (:error m) " errors"))
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(t/run-tests 'xz.portable-test)
