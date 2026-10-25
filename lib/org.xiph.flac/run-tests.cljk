(ns run-tests
  "Runs the runtime-agnostic FLAC suite on ClojureScript via nbb.

   org-microsoft-riff comes from the sibling checkout and is used only to read
   the reference decoder's WAV output; src/ has no dependencies."
  (:require [cljs.test :as t]
            [flac.flac-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\nnbb: " (:test m) " tests, " (:pass m) " passed, "
                (:fail m) " failed, " (:error m) " errors"))
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(t/run-tests 'flac.flac-test)
