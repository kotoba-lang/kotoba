(ns kotobase.server.security.keywrap
  "RFC 9180 HPKE wrapping for serialized DEK keyrings."
  (:require [kotobase.cacao :as cacao]
            [hpke.core :as hpke]
            [hpke.dhkem :as dhkem]))

(def ^:private kem dhkem/x25519-hkdf-sha256)

(defn- random-ikm []
  (let [bytes (js/Uint8Array. 32)]
    (.getRandomValues js/crypto bytes)
    (vec bytes)))

(defn- utf8-vec [s]
  (vec (js/Uint8Array. (.encode (js/TextEncoder.) s))))

(defn- bytes-vec [^js b]
  (vec (array-seq b)))

(defn- vec->uint8 [v]
  (js/Uint8Array. (clj->js v)))

(defn- resolve! [result on-error]
  (if (= :ok (:status result))
    result
    (throw (ex-info on-error (select-keys result [:status :reason :detail])))))

(defn- derive-kp! [ikm]
  (let [r (dhkem/derive-key-pair kem ikm)]
    (resolve! r "hpke derive-key-pair failed")
    {:private (:private r) :public (:public r)}))

(defn generate-recipient-keypair []
  (let [kp (derive-kp! (random-ikm))]
    (js/Promise.resolve
     {:public-key-b64 (cacao/bytes->base64 (vec->uint8 (:public kp)))
      :private-key-b64 (cacao/bytes->base64 (vec->uint8 (:private kp)))})))

(defn wrap-keyring [public-key-b64 keyring context]
  (js/Promise.resolve
   (let [pk-r (bytes-vec (cacao/base64->bytes public-key-b64))
         info (utf8-vec (str "kotobase/keyring/v1\u0000" context))
         pt (utf8-vec (js/JSON.stringify (clj->js keyring)))
         eph (derive-kp! (random-ikm))
         sealed (resolve! (hpke/seal-base pk-r info info pt eph) "hpke seal failed")]
     {:version 1
      :suite "X25519-HKDF-SHA256-CHACHA20POLY1305"
      :enc (cacao/bytes->base64 (vec->uint8 (:enc sealed)))
      :ciphertext (cacao/bytes->base64 (vec->uint8 (:bytes sealed)))})))

(defn unwrap-keyring [private-key-b64 envelope context]
  (when-not (and (= 1 (:version envelope))
                 (= "X25519-HKDF-SHA256-CHACHA20POLY1305" (:suite envelope)))
    (throw (ex-info "unsupported wrapped keyring" {:type :keywrap-envelope-invalid})))
  (js/Promise.resolve
   (let [sk (bytes-vec (cacao/base64->bytes private-key-b64))
         pk (resolve! ((:pk-of kem) sk) "hpke public-key failed")
         kp-r {:private sk :public (:bytes pk)}
         info (utf8-vec (str "kotobase/keyring/v1\u0000" context))
         enc (bytes-vec (cacao/base64->bytes (:enc envelope)))
         ct (bytes-vec (cacao/base64->bytes (:ciphertext envelope)))
         opened (resolve! (hpke/open-base enc kp-r info info ct) "hpke open failed")
         plain (vec->uint8 (:bytes opened))]
     (js->clj (js/JSON.parse (.decode (js/TextDecoder.) plain))))))
