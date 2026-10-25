(ns hata.didkey-test
  "app DID → IPNS name の導出。ベクタは tech-ipfs-specs-ipns の core_test が
  持つ実値（pubkey (vec (range 32)) → k51qzi5...7127）で、照合は独立。"
  (:require [cljs.test :refer [deftest is testing]]
            [hata.didkey :as didkey]))

(def pubkey (vec (range 32)))

;; ipns.core/core_test の実測ベクタ
(def expected-name "k51qzi5uqu5dg6lcd99r9gmb963kgugjinxxggwy7o93oagk3f2eg3qcjh7127")

(deftest a-did-key-round-trips-its-pubkey
  (let [did (didkey/pubkey->did-key pubkey)]
    (is (.startsWith did "did:key:z"))
    (is (= pubkey (didkey/did-key-pubkey did)))))

(deftest the-ipns-name-is-derived-not-guessed
  (is (= expected-name (didkey/did-key->ipns-name (didkey/pubkey->did-key pubkey)))))

(deftest a-foreign-key-form-derives-nothing
  ;; secp256k1-pub (0xe7) must not be read as ed25519
  (is (nil? (didkey/did-key-pubkey "did:key:zQ3shw764a1MpUvqqd1UqfPmvD9c7hBvq7W8m9oPnExample")))
  (is (nil? (didkey/did-key->ipns-name "not-a-did")))
  (is (nil? (didkey/did-key->ipns-name "did:key:z")))
  (is (nil? (didkey/did-key-pubkey "did:web:example.com"))))
