(ns viber.signature-test
  (:require [clojure.test :refer [deftest is]]
            [viber.signature :as sig]))

;; Known-answer: HMAC-SHA256("secret", "hello") hex -- SAME known-answer
;; value com-meta-webhook's signature_test.clj uses (identical algorithm,
;; different key/message roles don't change the digest computation itself,
;; computed independently: python3 -c "import hmac,hashlib;
;; print(hmac.new(b'secret', b'hello', hashlib.sha256).hexdigest())")
(def known-answer-hex "88aab3ede8d3adf94d26ab90d3bafd4a2083070c3bcce9c014ee04a443847c0b")

(deftest hmac-sha256-hex-matches-known-answer
  (is (= known-answer-hex (sig/hmac-sha256-hex "secret" "hello"))))

(deftest valid-signature-true-for-matching-signature-no-prefix
  ;; Viber's header has NO "sha256=" prefix, unlike Meta's scheme --
  ;; verifies the raw hex compares directly.
  (is (true? (sig/valid-signature? "secret" "hello" known-answer-hex))))

(deftest valid-signature-false-for-wrong-token
  (is (false? (sig/valid-signature? "wrong-token" "hello" known-answer-hex))))

(deftest valid-signature-false-for-tampered-body
  (is (false? (sig/valid-signature? "secret" "hello!" known-answer-hex))))
