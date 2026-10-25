(ns provider.value-codec-test
  (:require [clojure.test :refer [deftest is testing]]
            [provider.value-codec :as codec]))

(deftest typed-audit-value-round-trips
  (let [bytes (codec/encode-audit-value
               :http :request
               {:url "https://example.test" :headers #{:accept :host}})]
    (is (= {:format :provider.ops-audit/v1
            :kit :http
            :direction :request
            :value {:url "https://example.test" :headers #{:accept :host}}}
           (codec/decode-audit-value bytes)))))

(deftest legacy-edn-is-only-a-bounded-compatibility-input
  (let [bytes (codec/legacy-edn->audit-bytes
               :secret :reply
               "{:tag :value :value \"s3cr3t\"}")]
    (is (= {:format :provider.ops-audit/v1
            :kit :secret
            :direction :reply
            :value {:tag :value :value "s3cr3t"}}
           (codec/decode-audit-value bytes))))
  (testing "tagged literals and over-limit text fail closed"
    (is (thrown? Exception
                 (codec/legacy-edn->audit-bytes :http :request "#foo/bar 1")))
    (is (thrown? Exception
                 (codec/legacy-edn->audit-bytes
                  :http :request
                  (apply str (repeat (inc codec/max-audit-value-bytes) "x")))))))

(deftest envelope-shape-is-validated
  (is (thrown? Exception (codec/encode-audit-value "http" :request {})))
  (is (thrown? Exception (codec/encode-audit-value :http :sideways {}))))
