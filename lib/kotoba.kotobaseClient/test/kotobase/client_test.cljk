(ns kotobase.client-test
  (:require [cljs.test :refer-macros [deftest is testing]]
            [kotoba.lang.text :as str]
            [kotobase.client :as client]))

(deftest decode-edn-scalar-cases
  (testing "EDN row cells → cljs scalars (SDK decodeEdnScalar parity)"
    (is (= "hi" (client/decode-edn-scalar "\"hi\"")))
    (is (= "" (client/decode-edn-scalar "")))
    (is (= 42 (client/decode-edn-scalar "42")))
    (is (= -7 (client/decode-edn-scalar "-7")))
    (is (= 1.5 (client/decode-edn-scalar "1.5")))
    (is (true? (client/decode-edn-scalar "true")))
    (is (false? (client/decode-edn-scalar "false")))
    (is (nil? (client/decode-edn-scalar "nil")))
    (is (= ":yoro.post/uri" (client/decode-edn-scalar ":yoro.post/uri"))
        "keywords kept as their EDN string")
    (is (= 5 (client/decode-edn-scalar 5)) "non-string passthrough")))

(deftest make-client-derives-operator-did
  (let [c (client/make-client {:endpoint "https://kotobase.net/"
                               :secret-key (js/Uint8Array.from (clj->js (range 32)))
                               :operator-did "did:web:kotobase.net"})]
    (is (= "https://kotobase.net" (:endpoint c)) "trailing slash trimmed")
    (is (str/starts-with? (:did c) "did:key:z6Mk"))))
