(ns run-tests
  "Runs the runtime-agnostic WOFF/WOFF2 suites on ClojureScript via nbb.

   Sibling checkouts supply the dependencies (nbb has no resolver): brotli for
   WOFF2's compressed block, deflate for WOFF 1.0's per-table zlib, and
   org-iso-opentype for the metadata parse. The JVM suite adds the conformance
   sweep against the reference woff2 tools."
  (:require [cljs.test :as t]
            [woff.woff2-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\nnbb: " (:test m) " tests, " (:pass m) " passed, "
                (:fail m) " failed, " (:error m) " errors"))
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(t/run-tests 'woff.woff2-test)
