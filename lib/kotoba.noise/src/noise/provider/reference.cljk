(ns noise.provider.reference
  "ClojureScript provider that routes AEAD through first-party
  `chacha20.aead` and SHA-256 through `sha2.core`, while keeping X25519
  and BLAKE2s on `provider/noble`.

  This is the **correctness / CI** path for `@noble/ciphers` and
  `@noble/hashes` (SHA-256 only) substitution (ADR-2608301100): portable
  crypto + explicit provider, not deleting `@noble/*` from package.json on
  hot paths. Production handshakes should keep `provider/node` or
  `provider/noble` for speed — see `provider/node` docstring for measured
  costs."
  (:require [chacha20.aead :as aead]
            [noise.hash.reference :as hash-ref]
            [noise.provider.noble :as noble]))

(defn aead-encrypt [k nonce ad plaintext]
  (aead/seal! k nonce ad plaintext))

(defn aead-decrypt [k nonce ad ciphertext]
  (let [r (aead/open k nonce ad ciphertext)]
    (when (= :ok (:status r)) (:bytes r))))

(defn- hash-fn [{:keys [hash] :or {hash :blake2s}}]
  (if (= hash :sha256)
    (fn [bs] (vec (js/Array.from (hash-ref/sha256 (js/Uint8Array.from (clj->js bs))))))
    (:hash (noble/ports {:hash hash}))))

(defn ports
  ([] (ports {}))
  ([opts]
   (let [base (noble/ports opts)
         h (hash-fn opts)]
     (assoc base
            :aead-encrypt aead-encrypt
            :aead-decrypt aead-decrypt
            :hash h))))
