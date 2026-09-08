(ns kotoba.kagi-boundary-test
  "The JVM-only half: real-op-effects is Chicory wiring (kotoba.wasm-exec),
  not a kagi-boundary concern. The boundary's own portable coverage lives in
  kotoba.kagi-boundary-portable-test (.cljc), registered on both hosts."
  (:require [clojure.test :refer [deftest is]]
            [kotoba.wasm-exec :as wasm-exec]))

(deftest wasm-raw-private-key-effects-are-disabled-by-default
  (let [secure (wasm-exec/real-op-effects nil)]
    (is (= -1 ((get secure 'gen-keypair) nil nil)))
    (is (= -1 ((get secure 'sign) nil nil)))))
