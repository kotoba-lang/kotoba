(ns engi.crypto-test
  "Ed25519 sign/verify + CID round-trip tests (real @noble/curves, no
  network — pure crypto)."
  (:require [kotoba.lang.text :as str]
            [cljs.test :refer-macros [deftest is testing]]
            [engi.crypto :as crypto]))

(defn- flip-first-char
  "Corrupts a base64url string by changing its FIRST character (which always
  encodes high-order bits of the first byte, so the change is guaranteed to
  alter the decoded bytes) — flipping the LAST character of a base64url
  Ed25519 signature (512 bits = 85.33 base64 chars) can, depending on which
  bits fall in the trailing zero-padding region, decode to the SAME bytes
  and leave the signature verifying as still valid, which is not a useful
  tamper test."
  [^string s]
  (let [c0 (subs s 0 1)
        flipped (if (= c0 "A") "B" "A")]
    (str flipped (subs s 1))))

(deftest identity-roundtrip
  (let [{:keys [did]} (crypto/generate-identity)]
    (is (str/starts-with? did "did:key:z"))))

(deftest transfer-id-deterministic
  (let [body {:spender "did:key:zA" :receiver "did:key:zB" :amount 10
              :spender-prev "genesis" :nonce "n1" :ts 1000}]
    (is (= (crypto/transfer-id body) (crypto/transfer-id body)))
    (is (not= (crypto/transfer-id body) (crypto/transfer-id (assoc body :amount 11))))))

(deftest sign-transfer-verify-roundtrip
  (let [spender (crypto/generate-identity)
        body {:spender (:did spender) :receiver "did:key:zB" :amount 42
              :spender-prev "genesis" :nonce "n1" :ts 1000}
        {:keys [transfer-id sig]} (crypto/sign-transfer body (:secret-key spender))]
    (testing "valid signature verifies"
      (is (true? (crypto/verify-transfer-id-sig transfer-id sig (:did spender)))))
    (testing "tampered transfer-id rejects"
      (is (false? (crypto/verify-transfer-id-sig "some-other-cid" sig (:did spender)))))
    (testing "tampered signature rejects"
      (is (false? (crypto/verify-transfer-id-sig transfer-id (flip-first-char sig) (:did spender)))))
    (testing "wrong signer rejects"
      (let [other (crypto/generate-identity)]
        (is (false? (crypto/verify-transfer-id-sig transfer-id sig (:did other))))))))

(deftest sign-transfer-tampered-sig-rejects-2
  (let [spender (crypto/generate-identity)
        body {:spender (:did spender) :receiver "did:key:zB" :amount 1
              :spender-prev "genesis" :nonce "n" :ts 1}
        {:keys [transfer-id sig]} (crypto/sign-transfer body (:secret-key spender))
        tampered (flip-first-char sig)]
    (is (not= sig tampered))
    (is (false? (crypto/verify-transfer-id-sig transfer-id tampered (:did spender))))))

(deftest entry-hash-deterministic-and-sensitive
  (let [entry {:engi/kind "debit" :engi/seq 0 :engi/prev-hash "genesis"
               :engi/counterparty "did:key:zB" :engi/amount 5 :engi/memo nil
               :engi/transfer-id "cid1" :engi/self-sig "sigA" :engi/counter-sig "sigB"
               :engi/ts 1000}]
    (is (= (crypto/entry-hash entry) (crypto/entry-hash entry)))
    (is (not= (crypto/entry-hash entry) (crypto/entry-hash (assoc entry :engi/amount 6))))))

(deftest verify-self-sig-and-counter-sig
  (let [spender (crypto/generate-identity)
        receiver (crypto/generate-identity)
        body {:spender (:did spender) :receiver (:did receiver) :amount 7
              :spender-prev "genesis" :nonce "n" :ts 1}
        {:keys [transfer-id sig]} (crypto/sign-transfer body (:secret-key spender))
        counter-sig (crypto/sign-transfer-id transfer-id (:secret-key receiver))
        debit-entry {:engi/kind "debit" :engi/seq 0 :engi/prev-hash "genesis"
                      :engi/counterparty (:did receiver) :engi/amount 7 :engi/memo nil
                      :engi/transfer-id transfer-id :engi/self-sig sig :engi/counter-sig counter-sig
                      :engi/ts 1}]
    (is (true? (crypto/verify-self-sig debit-entry (:did spender))))
    (is (true? (crypto/verify-counter-sig debit-entry)))
    (is (false? (crypto/verify-self-sig debit-entry (:did receiver))) "wrong owner-did rejects")))
