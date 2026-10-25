(ns run-tests
  "Runs the runtime-agnostic bzip2 suite on ClojureScript via nbb.

   Zero dependencies, so there is nothing to fetch: the portable suite carries
   recorded reference streams and needs no shell. The JVM suite adds the sweep
   that feeds our output back to the `bzip2` binary."
  (:require [cljs.test :as t]
            [bzip2.bzip2-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\nnbb: " (:test m) " tests, " (:pass m) " passed, "
                (:fail m) " failed, " (:error m) " errors"))
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(t/run-tests 'bzip2.bzip2-test)
