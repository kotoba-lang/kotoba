(ns kotoba.kagi-boundary-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.kagi-boundary :as boundary]
            [kotoba.wasm-exec :as wasm-exec]))

(deftest kotoba-persists-only-kagi-references
  (let [r (boundary/reference-record {:ref "kagi://personal/github"
                                      :category :login :purpose :deploy :key-epoch 4})]
    (is (= "kagi://personal/github" (:kotoba.secret/ref r)))
    (is (= r (boundary/assert-reference-only! r)))
    (is (thrown? Exception
                 (boundary/assert-reference-only! (assoc r :plaintext "leak"))))))

(deftest wasm-raw-private-key-effects-are-disabled-by-default
  (let [secure (wasm-exec/real-op-effects nil)]
    (is (= -1 ((get secure 'gen-keypair) nil nil)))
    (is (= -1 ((get secure 'sign) nil nil)))))
