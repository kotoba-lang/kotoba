(ns run-tests
  "Runs the runtime-agnostic SHA-2 suite on ClojureScript via nbb.

   The JVM suite adds the oracle sweep against java.security.MessageDigest and
   the shasum binary."
  (:require [cljs.test :as t]
            [sha2.sha2-test]
            [sha2.sha512-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\nnbb: " (:test m) " tests, " (:pass m) " passed, "
                (:fail m) " failed, " (:error m) " errors"))
  (when-not (t/successful? m) (set! (.-exitCode js/process) 1)))

(t/run-tests 'sha2.sha2-test 'sha2.sha512-test)
