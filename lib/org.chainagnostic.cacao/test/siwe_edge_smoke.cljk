(ns siwe-edge-smoke
  (:require [siwe.core :as core]
            [siwe.edge :as edge]
            ["@noble/curves/secp256k1.js" :refer [secp256k1]]
            ["@noble/hashes/sha3.js" :refer [keccak_256]]))

(def failures (atom 0))
(defn check [label truth]
  (println (if truth "ok  " "FAIL") label)
  (when-not truth (swap! failures inc)))

(defn hex [bytes]
  (apply str (map #(let [h (.toString % 16)] (if (= 1 (count h)) (str "0" h) h))
                  (array-seq bytes))))

(def private-key
  (js/Uint8Array.from
   #js [1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16
        17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32]))

(def public-key (secp256k1.getPublicKey private-key false))
(def address (edge/checksum-address (str "0x" (subs (hex (keccak_256 (.slice public-key 1))) 24))))
(def issued "2026-08-26T03:00:00Z")
(def expires "2026-08-26T03:05:00Z")
(def message
  (core/format-message
   {:scheme "https" :domain "auth.kotobase.net" :address address
    :statement "Sign in to kotobase. This request does not send a transaction."
    :uri "https://auth.kotobase.net/sign-in" :version "1" :chain-id "1"
    :nonce "AbCdEf1234567890" :issued-at issued :expiration-time expires
    :resources ["https://kotobase.net/"]}))
(def recovered-signature
  (secp256k1.sign (edge/eip191-digest message) private-key
                  #js {:prehash false :lowS true :format "recovered"}))
(def ethereum-signature
  (let [out (js/Uint8Array. 65)]
    (.set out (.slice recovered-signature 1) 0)
    (aset out 64 (+ 27 (aget recovered-signature 0)))
    (str "0x" (hex out))))
(def expected {:scheme "https" :domain "auth.kotobase.net"
               :uri "https://auth.kotobase.net/sign-in"
               :nonce "AbCdEf1234567890" :chain-ids #{"1"}
               :now-sec (/ (js/Date.parse "2026-08-26T03:02:00Z") 1000)
               :max-age-sec 300 :require-expiration? true})

(let [verified (edge/verify message ethereum-signature expected)]
  (check "EIP-191 secp256k1 signature recovers the claimed address" (:valid? verified))
  (check "session principal is chain-bound did:pkh"
         (= (str "did:pkh:eip155:1:" (.toLowerCase address)) (:principal verified)))
  (check "wrong relying-party domain rejects"
         (= :domain-mismatch (:problem (edge/verify message ethereum-signature
                                                     (assoc expected :domain "evil.example")))))
  (check "wrong nonce rejects"
         (= :nonce-mismatch (:problem (edge/verify message ethereum-signature
                                                   (assoc expected :nonce "OtherNonce123")))))
  (check "expired message rejects"
         (= :message-too-old
            (:problem (edge/verify message ethereum-signature
                                   (assoc expected :now-sec
                                          (/ (js/Date.parse "2026-08-26T04:00:00Z") 1000))))))
  (check "message tampering invalidates signature"
         (= :signature-address-mismatch
            (:problem (edge/verify (.replace message "Chain ID: 1" "Chain ID: 8453")
                                   ethereum-signature
                                   (assoc expected :chain-ids #{"8453"}))))))

(when (pos? @failures) (js/process.exit 1))
