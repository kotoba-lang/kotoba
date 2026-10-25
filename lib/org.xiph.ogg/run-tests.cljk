(ns run-tests
  "Runs the runtime-agnostic Ogg suite on ClojureScript via nbb.

   Zero dependencies: the recorded reference containers are checked in, so there
   is nothing to fetch. The JVM suite adds the ffmpeg oracle."
  (:require [cljs.test :as t]
            [ogg.ogg-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\nnbb: " (:test m) " tests, " (:pass m) " passed, "
                (:fail m) " failed, " (:error m) " errors"))
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(t/run-tests 'ogg.ogg-test)
