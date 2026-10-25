(ns feishu.signature-test
  (:require [clojure.test :refer [deftest testing is]]
            [feishu.signature :as sig]))

(deftest token-valid?-test
  (testing "matching token"
    (is (true? (sig/token-valid? "expected-tok" "expected-tok"))))
  (testing "mismatched token"
    (is (false? (sig/token-valid? "expected-tok" "wrong-tok"))))
  (testing "nil actual token (never a truthy match)"
    (is (false? (sig/token-valid? "expected-tok" nil)))))

(deftest valid-signature?-known-answer-test
  (let [ctx {:timestamp "1700000000" :nonce "abc123" :encrypt-key "my-encrypt-key" :body "{\"foo\":\"bar\"}"}
        good-sig (sig/sha256-hex (str (:timestamp ctx) (:nonce ctx) (:encrypt-key ctx) (:body ctx)))]
    (testing "matching signature"
      (is (true? (sig/valid-signature? ctx good-sig))))
    (testing "wrong signature"
      (is (false? (sig/valid-signature? ctx "0000000000000000000000000000000000000000000000000000000000000000"))))
    (testing "wrong body -> signature no longer matches"
      (is (false? (sig/valid-signature? (assoc ctx :body "{\"foo\":\"tampered\"}") good-sig))))
    (testing "nil signature header"
      (is (false? (sig/valid-signature? ctx nil))))))
