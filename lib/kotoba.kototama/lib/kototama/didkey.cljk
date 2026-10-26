(ns kototama.didkey
  "kototama.didkey — the PORTABLE encoding half of a self-certifying did:key (Ed25519). An
  actor self-generates its OWN keypair (the keygen/sign/verify live in actor:host — they
  need platform crypto; see kototama.host), but the *encoding* of a raw 32-byte public key into
  `did:key:z6Mk…` is pure byte math and lives here, shared across every kototama.

  did:key (Ed25519) = multicodec 0xed 0x01 ++ raw-pubkey, multibase base58btc ('z' prefix).
  base58btc is INLINED (no dependency) so this is portable to bb/JVM today and to the
  kototama wasm subset as the host gains byte-vector ops. Deterministic; pure."
  (:require [kotoba.lang.text :as str]))

(def ^:private b58-alphabet "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")

(defn base58btc
  "Encode a byte seq as base58btc (Bitcoin alphabet, no checksum), leading-zero bytes → '1'."
  [bs]
  (let [bs (mapv #(bit-and (long %) 0xff) (seq bs))
        zeros (count (take-while zero? bs))
        digits (loop [src (vec (drop zeros bs)) out []]
                 (if (empty? src)
                   out
                   (let [[q r] (reduce (fn [[acc carry] b]
                                         (let [cur (+ (* carry 256) b)]
                                           [(conj acc (quot cur 58)) (mod cur 58)]))
                                       [[] 0] src)]
                     (recur (vec (drop-while zero? q)) (conj out r)))))]
    (str (apply str (repeat zeros \1))
         (apply str (map #(nth b58-alphabet %) (reverse digits))))))

(defn did-key
  "Raw 32-byte Ed25519 public key → `did:key:z…` (multicodec 0xed01 + base58btc). Always
  begins `did:key:z6Mk` for Ed25519."
  [pub32]
  (str "did:key:z" (base58btc (concat [0xed 0x01] (seq pub32)))))

(defn attest-message
  "The message an actor signs to self-certify its did.json CID (kanae diddoc-attest pattern):
  `did:key|<cid>`. The server never signs; only the actor's own key does (actor:host/sign),
  and anyone verifies with the public did:key."
  [did diddoc-cid]
  (str did "|" diddoc-cid))
