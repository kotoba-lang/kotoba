(ns kotoba.lang.crypto
  "Cryptographic primitives: hash (sha2-256/512), HMAC, HKDF, AEAD shape.
  Portable — uses java.security.MessageDigest (SHA-2) on the JVM, and a
  host-injected digest fn on WASM (no native crypto baked in). The AEAD
  interface is a data contract (encrypt/decrypt return ciphertext+tag maps);
  the cipher itself is host-injected. Consumed by cacao/kotobase auth chains.
  No third-party deps; .cljc (JVM/SCI/CLJS/GraalVM/kotoba-WASM)."
  (:refer-clojure :exclude [hash])
  (:require [kotoba.crypto.aead :as aead-p]))

(defn- jvm-digest [algo data]
  #?(:clj  (let [md (java.security.MessageDigest/getInstance algo)]
             (.digest md (byte-array data)))
     :cljs (throw (ex-info "crypto: WASM/CLJS digest needs host-injected fn" {:algo algo}))))

(defn- ->bytes
  "byte-array under :clj; plain vector-of-ints under :cljs (no byte-array
  there — see kotoba-lang/io-multiformats.core for the established
  precedent)."
  [xs]
  #?(:clj (byte-array xs) :cljs (vec xs)))

(def default-digest-fn
  "Default digest fn (JVM MessageDigest). On WASM, inject a host fn."
  (fn [algo data]
    (jvm-digest (case algo :sha256 "SHA-256" :sha512 "SHA-512" "SHA-256") data)))

(defn hash
  "Hash `data` (byte seq) with `algo` (:sha256 default, :sha512). Returns a byte
  array. Uses the default JVM digest fn unless `:digest-fn` is supplied."
  ([data] (hash :sha256 data))
  ([algo data] (hash algo data default-digest-fn))
  ([algo data digest-fn]
   (digest-fn algo (vec data))))

(defn hmac
  "HMAC-SHA-256 of `data` with `key`. Returns a byte array. Pure: HMAC = H(K ⊕
  opad || H(K ⊕ ipad || data)) where H is sha-256. Portable (only needs the
  digest fn)."
  ([key data] (hmac key data default-digest-fn))
  ([key data digest-fn]
  (let [block-size 64
        k (vec key)
        k (if (> (count k) block-size) (vec (hash :sha256 k digest-fn)) k)
        k (concat k (repeat (- block-size (count k)) 0))
        ipad (map bit-xor k (repeat block-size 0x36))
        opad (map bit-xor k (repeat block-size 0x5C))
        inner (hash :sha256 (concat ipad data) digest-fn)
        outer (hash :sha256 (concat opad inner) digest-fn)]
    (->bytes outer))))

(defn hkdf
  "HKDF-SHA-256: extract+expand `ikm` (input keying material) and `info` (context)
  to `length` bytes. Returns a byte array. Pure (only needs digest fn)."
  ([ikm info length] (hkdf ikm info length default-digest-fn))
  ([ikm info length digest-fn]
   (let [prk (hmac (vec (repeat 32 0)) ikm digest-fn)   ; extract
         ;; expand: T(1) = HMAC(prk, T(0) || info || 0x01), T(n) = HMAC(prk, T(n-1) || info || n)
         hash-len 32
         n (max 1 (Math/ceil (/ length hash-len)))
         blocks (loop [i 1 t [] out (transient [])]
                  (if (> i n)
                    (persistent! out)
                    (let [input (concat t (vec info) [(if (< i 255) i (unchecked-byte i))])
                          t' (hmac prk input digest-fn)]
                      (recur (inc i) (vec t') (conj! out t')))))
         all (apply concat blocks)]
     (->bytes (take length all)))))

;; ---------- AEAD (data contract; cipher is host-injected) ----------

(def IAEAD
  "The protocol itself lives in one repo of its own now. This name is that
  SAME protocol, not a second one: an implementation reified against either
  is accepted by both (ADR-2609091900)."
  aead-p/AEAD)

(def decrypt aead-p/decrypt)
(def encrypt aead-p/encrypt)

(defn mock-aead
  "A trivial AEAD for tests (XOR + HMAC tag). NOT secure — for testing only."
  []
  (reify IAEAD
    (encrypt [_ key nonce plaintext aad]
      (let [ct (->bytes (map bit-xor plaintext (cycle key)))
            tag (hmac (vec key) (concat (vec nonce) (vec aad) (vec ct)))]
        {:ciphertext ct :tag tag}))
    (decrypt [_ key nonce ciphertext tag aad]
      (let [expected (hmac (vec key) (concat (vec nonce) (vec aad) (vec ciphertext)))]
        (if (= (vec expected) (vec tag))
          (->bytes (map bit-xor ciphertext (cycle key)))
          (throw (ex-info "crypto: AEAD auth failed" {})))))))

;; ---------- provider metadata + envelope emission ----------
;; Crypto-agility contract (kotoba-lang/kotoba#264): every produced envelope
;; must carry provider and algorithm metadata so the security policy gate
;; (kotoba.security.crypto-policy/check-envelope) can validate it under
;; :crypto-agile / :hybrid-required / :fips-required modes.

(defn validate-provider
  "Validates a host-injected provider record. Required: :provider/id (keyword)
  and :provider/fips-validated (boolean — an explicit false is required; FIPS
  status must never be implicit). Optional: :provider/algorithms (non-empty
  vector of keywords) naming the algorithms the provider implements. Returns
  the provider, or throws ex-info."
  [provider]
  (when-not (map? provider)
    (throw (ex-info "crypto: provider record required" {:provider provider})))
  (when-not (keyword? (:provider/id provider))
    (throw (ex-info "crypto: provider id required" {:provider provider})))
  (when-not (boolean? (:provider/fips-validated provider))
    (throw (ex-info "crypto: provider fips-validated flag required"
                    {:provider provider})))
  (when (and (contains? provider :provider/algorithms)
             (not (and (vector? (:provider/algorithms provider))
                       (seq (:provider/algorithms provider))
                       (every? keyword? (:provider/algorithms provider)))))
    (throw (ex-info "crypto: provider algorithms must be a non-empty vector of keywords"
                    {:provider provider})))
  provider)

(defn envelope-metadata
  "Builds the :envelope/* metadata map every produced envelope must carry:
  {:envelope/algorithms [..] :envelope/provider {:provider/id .. :provider/fips-validated ..}
   :envelope/epoch int :envelope/kem? bool :envelope/hybrid? bool}.
  `algorithms` is a non-empty seq of keywords; `opts` may set :epoch
  (default 0), :kem? and :hybrid? (default false). Validates the provider."
  ([provider algorithms] (envelope-metadata provider algorithms {}))
  ([provider algorithms {:keys [epoch kem? hybrid?]
                         :or {epoch 0 kem? false hybrid? false}}]
   (validate-provider provider)
   (when-not (and (seq algorithms) (every? keyword? algorithms))
     (throw (ex-info "crypto: envelope algorithms required" {:algorithms algorithms})))
   (when-not (int? epoch)
     (throw (ex-info "crypto: envelope epoch must be an int" {:epoch epoch})))
   {:envelope/algorithms (vec algorithms)
    :envelope/provider (select-keys provider [:provider/id :provider/fips-validated])
    :envelope/epoch epoch
    :envelope/kem? (boolean kem?)
    :envelope/hybrid? (boolean hybrid?)}))

(defn aead-provider
  "Registers a host-injected AEAD cipher with its provider metadata (the
  injection boundary). Validates the provider record at registration —
  hosts cannot inject a cipher without declaring :provider/id and
  :provider/fips-validated. Returns {:aead .. :provider ..}."
  [aead provider]
  (when-not (satisfies? IAEAD aead)
    (throw (ex-info "crypto: AEAD implementation required" {:aead aead})))
  {:aead aead :provider (validate-provider provider)})

(defn seal
  "Encrypts with a registered AEAD provider (see `aead-provider`) and returns
  an envelope map carrying the ciphertext plus :envelope/* metadata:
  {:ciphertext bytes :tag bytes :envelope/algorithms .. :envelope/provider ..
   :envelope/epoch .. :envelope/kem? .. :envelope/hybrid? ..}.
  Algorithms default to the provider's :provider/algorithms; `opts` may set
  :algorithms, :epoch (default 0), :kem?, :hybrid? (default false)."
  ([registered key nonce plaintext aad]
   (seal registered key nonce plaintext aad {}))
  ([registered key nonce plaintext aad opts]
   (let [{:keys [aead provider]} registered
         algorithms (or (:algorithms opts) (:provider/algorithms provider))]
     (merge (encrypt aead key nonce plaintext aad)
            (envelope-metadata provider algorithms opts)))))

(defn unseal
  "Decrypts an envelope map produced by `seal`. Returns plaintext bytes, or
  throws on auth failure."
  [registered key nonce envelope aad]
  (decrypt (:aead registered) key nonce
           (:ciphertext envelope) (:tag envelope) aad))
