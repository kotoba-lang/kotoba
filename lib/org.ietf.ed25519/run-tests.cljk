(ns run-tests
  "Runs the runtime-agnostic Ed25519 suite on ClojureScript via nbb.

   Not a formality: the field underneath is a `long-array` on the JVM and a
   `Float64Array` here, SHA-512's words are `[hi lo]` pairs whose arithmetic
   is a different instruction sequence on each, and the scalar reduction's
   floor division is the one place `quot` differs from what it needs to be.

   The JVM suite adds the differential sweep against BouncyCastle."
  (:require [cljs.test :as t]
            [ed25519.sign-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\nnbb: " (:test m) " tests, " (:pass m) " passed, "
                (:fail m) " failed, " (:error m) " errors"))
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(t/run-tests 'ed25519.sign-test)
