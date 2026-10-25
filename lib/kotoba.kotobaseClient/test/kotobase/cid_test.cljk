(ns kotobase.cid-test
  (:require [cljs.test :refer-macros [deftest is testing]]
            [kotoba.lang.text :as str]
            ["@noble/curves/ed25519.js" :refer [ed25519]]
            [kotobase.cid :as cid]))

;; Deterministic 32-byte Ed25519 seed (0,1,2,...,31).
(def seed (js/Uint8Array.from (clj->js (range 32))))

(deftest did-key-format
  (testing "Ed25519 did:key has the z6Mk multicodec prefix"
    (let [pub (.getPublicKey ed25519 seed)
          did (cid/did-key-from-ed25519-pub pub)]
      ;; 0xed01 multicodec on a 32-byte key always base58btc-encodes to z6Mk…
      (is (str/starts-with? did "did:key:z6Mk"))
      ;; ed25519 did:key is "did:key:" (8) + ~48-char base58 payload.
      (is (<= 55 (count did) 57)))))

(deftest did-key-rejects-bad-length
  (is (thrown? js/Error (cid/did-key-from-ed25519-pub (js/Uint8Array. 31)))))

(deftest graph-cid-format
  (testing "CIDv1/dag-cbor/sha2-256 graph handle is base32 'bafyrei…'"
    (let [g (cid/graph-cid-from-name "kotobase/db/did:key:zTest/people")]
      ;; 0x01 0x71 0x12 0x20 header → base32-lower always starts 'bafyrei'.
      (is (str/starts-with? g "bafyrei"))
      ;; 'b' + base32(36 bytes) = 1 + ceil(36*8/5) = 1 + 58 = 59 chars.
      (is (= 59 (count g))))))

(deftest base58-decode-roundtrip
  (let [b (js/Uint8Array.from (clj->js [0 0 1 2 250 255 13 7 0]))]
    (is (= (vec (array-seq b))
           (vec (array-seq (cid/base58btc-decode (cid/base58btc b)))))
        "leading zeros preserved")))

(deftest did-key-pub-roundtrip
  (let [pub (.getPublicKey ed25519 seed)
        did (cid/did-key-from-ed25519-pub pub)]
    (is (= (vec (array-seq pub)) (vec (array-seq (cid/did-key->ed25519-pub did))))
        "pub → did:key → pub round-trips")
    (is (nil? (cid/did-key->ed25519-pub "did:web:x")) "non-did:key → nil")))

(deftest did-key-with-malformed-base58-payload-returns-nil
  (testing "a did:key:z... string whose base58 payload contains a
            character outside the base58btc alphabet (base58btc-decode
            itself throws) must still resolve to nil, per this fn's own
            \"or nil when the DID isn't an Ed25519 did:key\" contract --
            not propagate a raw uncaught exception"
    (is (nil? (cid/did-key->ed25519-pub "did:key:zInvalid0DID")))
    (is (nil? (cid/did-key->ed25519-pub "did:key:zOI0lIllegalChars")))))

(deftest base32-lower-no-pad-rfc4648-vectors
  (testing "the RFC4648 §10 test vectors (base32, padding stripped, then
            lowercased to match this fn's alphabet) -- byte lengths 0..6
            exercise every bit-alignment case the 5-bit-group accumulator
            can hit, including the exact-multiple-of-5-bits boundary
            (5 bytes = 40 bits = 8 whole groups, no leftover bits at all)
            and the immediately-following case (6 bytes, 3 leftover bits)"
    (let [->bytes (fn [^string s] (js/Uint8Array.from (.encode (js/TextEncoder.) s)))]
      (is (= ""           (cid/base32-lower-no-pad (->bytes ""))))
      (is (= "my"          (cid/base32-lower-no-pad (->bytes "f"))))
      (is (= "mzxq"        (cid/base32-lower-no-pad (->bytes "fo"))))
      (is (= "mzxw6"       (cid/base32-lower-no-pad (->bytes "foo"))))
      (is (= "mzxw6yq"     (cid/base32-lower-no-pad (->bytes "foob"))))
      (is (= "mzxw6ytb"    (cid/base32-lower-no-pad (->bytes "fooba")))
          "5 bytes = 40 bits = 8 whole 5-bit groups -- zero leftover bits")
      (is (= "mzxw6ytboi"  (cid/base32-lower-no-pad (->bytes "foobar")))))))

(deftest graph-cid-deterministic
  (let [a (cid/canonical-graph "did:key:zABC" "people")
        b (cid/canonical-graph "did:key:zABC" "people")
        c (cid/canonical-graph "did:key:zABC" "places")]
    (is (= a b) "same name → same CID")
    (is (not= a c) "different db-name → different CID")))

;; ── IPNS name → pubkey ─────────────────────────────────────────────────────
;;
;; `ipns-name->ed25519-pub` is a deliberate SECOND implementation of
;; `kotoba-lang/tech-ipfs-specs-ipns`'s portable `ipns.core/name->pubkey`
;; (this repo is consumed as a bare shadow-cljs :source-path, so a git dep
;; would not resolve in consumer builds -- see that fn's docstring). Two
;; copies of a codec drift; these are the mitigation. Every literal below is
;; copied from `ipns.core-test`, so a divergence in either repo fails here.

(defn- ->u8 [ints] (js/Uint8Array.from (clj->js ints)))

(deftest ipns-name-decode-golden-vectors
  (testing "byte-identical to the JVM ipns.core/name->pubkey for its own vectors"
    (is (= (vec (range 32))
           (vec (array-seq (cid/ipns-name->ed25519-pub
                            "k51qzi5uqu5dg6lcd99r9gmb963kgugjinxxggwy7o93oagk3f2eg3qcjh7127")))))
    (is (= (vec (repeat 32 0))
           (vec (array-seq (cid/ipns-name->ed25519-pub
                            "k51qzi5uqu5dg6l7sg2ssb5uefnq8g7g1d6n6j2zsio0o0k7snyb11p8myhxxc")))))
    (is (= (vec (repeat 32 0xff))
           (vec (array-seq (cid/ipns-name->ed25519-pub
                            "k51qzi5uqu5dmkadisduutrwhobhcd351viuwscvsltkaymqovgho5slq61rlr"))))))
  (testing "and to a name a real go-ipfs/Kubo node produced (ipns.core-test's own)"
    (is (= [0x92 0x2e 0x4d 0x13 0xf9 0x69 0xb0 0xcc 0x8d 0xe7 0x7c 0x13
            0xe8 0x95 0x82 0x80 0x27 0xc4 0xd7 0x79 0x73 0x7a 0xca 0xe7
            0x4e 0x5f 0x36 0x16 0x4e 0xc4 0x79 0xed]
           (vec (array-seq (cid/ipns-name->ed25519-pub
                            "k51qzi5uqu5djtr2a6bj7pjlv4gdl8zvv8eov1rhknh0vn9uj7ojrozknot04t")))))))

(deftest ipns-name-decode-fails-closed
  (testing "nil, never a throw, for everything malformed"
    (doseq [bad [nil "" "not-a-k-name" "k" "k51" "kzzz!!!"
                 ;; right prefix, wrong multibase body
                 "k000000000000000000000000000000000000000000000000000000000000"]]
      (is (nil? (cid/ipns-name->ed25519-pub bad)) (str "for " (pr-str bad))))))

(deftest ipns-name-matches-pub
  (let [name "k51qzi5uqu5dg6lcd99r9gmb963kgugjinxxggwy7o93oagk3f2eg3qcjh7127"
        pub  (->u8 (range 32))
        other (->u8 (reverse (range 32)))]
    (testing "the key a name names matches that name"
      (is (true? (cid/ipns-name-matches-pub? name pub))))
    (testing "any other key does not, however well-formed"
      (is (false? (cid/ipns-name-matches-pub? name other))))
    (testing "fails closed on malformed input rather than throwing"
      (is (false? (cid/ipns-name-matches-pub? name nil)))
      (is (false? (cid/ipns-name-matches-pub? nil pub)))
      (is (false? (cid/ipns-name-matches-pub? "not-a-k-name" pub)))
      (is (false? (cid/ipns-name-matches-pub? name (->u8 (range 31)))))
      (is (false? (cid/ipns-name-matches-pub? name (->u8 (range 33))))))))
