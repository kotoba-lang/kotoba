(ns run-tests
  "Runs the runtime-agnostic RIFF/WAVE suite on ClojureScript via nbb.

   Zero dependencies: the recorded reference files are checked in, so there is
   nothing to fetch. The JVM suite adds the ffmpeg oracle in both directions."
  (:require [cljs.test :as t]
            [riff.riff-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\nnbb: " (:test m) " tests, " (:pass m) " passed, "
                (:fail m) " failed, " (:error m) " errors"))
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(t/run-tests 'riff.riff-test)
