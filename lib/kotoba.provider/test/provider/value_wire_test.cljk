(ns provider.value-wire-test
  "ADR 0285: the guest decides the canonical audit bytes; the host only admits.

  The oracle is `provider.value-codec/encode-audit-value` — the host codec that
  ADR 0284 introduced. A guest byte sequence is accepted here only when it is
  equal to the host's, byte for byte. Nothing in this namespace compares EDN
  text: EDN is the compatibility input this slice is removing from the secret
  kit's canonical path, so using it as the oracle would prove the wrong thing.

  Needs Node and a resolvable browser-host. Without one, `invoke-export`
  returns `{:ok false :reason :browser-host-unavailable}`, the guest-facing
  deftests print a SKIP line and assert nothing — same convention as
  `provider.edn-codec-test`. The host-only deftests at the bottom
  (`host-admits-only-this-envelope`, `hex-round-trips-every-byte`) always run,
  so the admission rules stay guarded even on a machine with no Node."
  (:require [cbor.core :as cbor]
            [clojure.test :refer [deftest is testing]]
            [ipld.value :as ipld-value]
            [provider.edn-codec :as codec]
            [provider.value-codec :as value-codec]))

(defn- guest-available? []
  (:ok (codec/invoke-export :secret-value-wire :main [])))

;; `*ns*` is `user` while tests run, so name the namespace at macroexpansion —
;; a SKIP line that cannot say what skipped is not worth printing.
(defmacro ^:private with-guest [& body]
  (let [where (str *ns*)]
    `(if (guest-available?)
       (do ~@body)
       (println "SKIP" ~where "- browser-host unavailable"))))

(defn- hex [bytes]
  (apply str (map #(format "%02x" (bit-and % 0xff)) bytes)))

(deftest guest-main-self-check
  (with-guest
    (is (= -2407 (:value (codec/invoke-export :secret-value-wire :main [])))
        "package main asserts its own three envelopes and two reject paths")))

(deftest request-bytes-equal-the-host-codec
  (with-guest
    (doseq [name ["API_TOKEN" "a" "x-0123456789" (apply str (repeat 128 "k"))]]
      (let [guest (:value (codec/secret-request-value-hex name))
            host (value-codec/encode-audit-value :secret :request {:name name})]
        (is (= (hex host) guest)
            (str "guest request bytes differ from the host codec for " name))
        (is (= (seq host)
               (seq (value-codec/guest-hex->audit-bytes :secret :request guest)))
            "un-hexing the guest bytes must reproduce the host bytes")))))

(deftest reply-bytes-equal-the-host-codec
  (with-guest
    (testing "value arm"
      (doseq [v ["s3cr3t" "" "0123456789012345678901234567890"]]
        (is (= (hex (value-codec/encode-audit-value
                     :secret :reply {:tag :value :value v}))
               (:value (codec/secret-reply-value-value-hex v)))
            (str "guest reply-value bytes differ for " (pr-str v)))))
    (testing "error arm"
      (doseq [[c m] [["not-found" "missing"] ["denied" ""]]]
        (is (= (hex (value-codec/encode-audit-value
                     :secret :reply {:tag :error :code c :message m}))
               (:value (codec/secret-reply-error-value-hex c m)))
            (str "guest reply-error bytes differ for " c "/" m))))))

(deftest folded-constants-equal-what-the-guest-itself-encodes
  ;; The module writes the keyword forms of its closed names as literals so one
  ;; instance survives more calls. That is only safe while the literals are what
  ;; the module's own encoder produces, which is what this checks — otherwise a
  ;; hand-typed hex constant is an unreviewable magic number.
  (with-guest
    (doseq [[name expected]
            {"kit" "8205636b6974"
             "secret" "820566736563726574"
             "value" "82056576616c7565"
             "format" "820566666f726d6174"
             "provider.ops-audit/v1" "82057570726f76696465722e6f70732d61756469742f7631"
             "direction" "820569646972656374696f6e"
             "request" "82056772657175657374"
             "reply" "8205657265706c79"
             "name" "8205646e616d65"
             "tag" "820563746167"
             "error" "8205656572726f72"
             "code" "820564636f6465"
             "message" "8205676d657373616765"}]
      (is (= expected (:value (codec/invoke-export :secret-value-wire :kw_form [name])))
          (str "folded literal for :" name " is not what the guest encodes"))
      (is (= expected (hex (cbor/encode (ipld-value/value->form (keyword name)))))
          (str "folded literal for :" name " is not what the host codec encodes")))))

(deftest guest-rejects-fail-closed
  (with-guest
    (doseq [[label name] [["empty name" ""]
                          ["quote" "a\"b"]
                          ["backslash" "a\\b"]
                          ["non-ascii" "鍵"]
                          ["over 128" (apply str (repeat 129 "k"))]]]
      (is (= "" (:value (codec/secret-request-value-hex name)))
          (str "guest must fail closed on " label)))))

(deftest host-admits-only-this-envelope
  ;; The host un-hexes, it does not re-encode. So everything that makes the
  ;; bytes canonical has to be rejected here rather than repaired.
  (let [good (hex (value-codec/encode-audit-value :secret :request {:name "n"}))]
    (is (some? (value-codec/guest-hex->audit-bytes :secret :request good)))
    (testing "kit and direction must match what the caller expected"
      (is (thrown? Exception (value-codec/guest-hex->audit-bytes :http :request good)))
      (is (thrown? Exception (value-codec/guest-hex->audit-bytes :secret :reply good))))
    (testing "malformed hex"
      (is (thrown? Exception (value-codec/hex->bytes "abc")))
      (is (thrown? Exception (value-codec/hex->bytes "zz")))
      (is (thrown? Exception (value-codec/hex->bytes "AB"))
          "uppercase is rejected so one byte sequence has one spelling"))
    (testing "non-canonical map order is rejected, not sorted"
      ;; {:kit …} and {:direction …} swapped out of encoded-length order.
      (let [swapped (hex (cbor/encode
                          [19 [[[5 "direction"] [5 "request"]]
                               [[5 "kit"] [5 "secret"]]
                               [[5 "format"] [5 "provider.ops-audit/v1"]]
                               [[5 "value"] [19 [[[5 "name"] [4 "n"]]]]]]]))]
        (is (thrown? Exception
                     (value-codec/guest-hex->audit-bytes :secret :request swapped)))))))

(deftest hex-round-trips-every-byte
  (let [all (apply str (map #(format "%02x" %) (range 256)))
        bytes (value-codec/hex->bytes all)]
    (is (= 256 (count bytes)))
    (is (= (range 256) (map #(bit-and % 0xff) bytes)))))
