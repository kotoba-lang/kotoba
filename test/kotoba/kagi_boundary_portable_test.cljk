(ns kotoba.kagi-boundary-portable-test
  "The genuinely portable half of kotoba.kagi-boundary-test: the boundary
  itself (reference-record / assert-reference-only!) is plain data + ex-info,
  no host I/O. `wasm-raw-private-key-effects-are-disabled-by-default` stays
  in kotoba.kagi-boundary-test (.clj) because kotoba.wasm-exec/real-op-effects
  is Chicory wiring, not because kagi-boundary itself needs the JVM."
  (:require #?(:clj [clojure.test :refer [deftest is]]
               :cljs [cljs.test :refer [deftest is] :include-macros true])
            [kotoba.kagi-boundary :as boundary]))

(deftest kotoba-persists-only-kagi-references
  (let [r (boundary/reference-record {:ref "kagi://personal/github"
                                      :category :login :purpose :deploy :key-epoch 4})]
    (is (= "kagi://personal/github" (:kotoba.secret/ref r)))
    (is (= r (boundary/assert-reference-only! r)))
    (is (thrown? #?(:clj Exception :cljs js/Error)
                 (boundary/assert-reference-only! (assoc r :plaintext "leak"))))))
