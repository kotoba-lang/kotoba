(ns chacha20.xchacha
  "XChaCha20-Poly1305: HChaCha20 subkey + RFC 8439 AEAD with a 24-byte nonce.

  The inner nonce is twelve bytes: four zero bytes followed by the last eight
  bytes of the extended nonce, matching @noble/ciphers' construction."
  (:require [chacha20.aead :as aead]
            [chacha20.core :as core]))

(def key-bytes 32)
(def nonce-bytes 24)

(defn- inner-nonce [nonce24]
  (vec (concat [0 0 0 0] (subvec nonce24 16 24))))

(defn- check-params [key nonce24]
  (cond
    (not= key-bytes (count key)) {:status :error :reason :bad-key-length :length (count key)}
    (not= nonce-bytes (count nonce24)) {:status :error :reason :bad-nonce-length :length (count nonce24)}
    :else nil))

(defn- derive-subkey [key nonce24]
  (core/hchacha-subkey! key (subvec nonce24 0 16)))

(defn seal
  [key nonce24 aad plaintext]
  (let [key (vec key) nonce24 (vec nonce24) aad (vec (or aad [])) pt (vec plaintext)]
    (or (check-params key nonce24)
        (aead/seal (derive-subkey key nonce24) (inner-nonce nonce24) aad pt))))

(defn open
  [key nonce24 aad sealed]
  (let [key (vec key) nonce24 (vec nonce24) aad (vec (or aad [])) sealed (vec sealed)]
    (or (check-params key nonce24)
        (aead/open (derive-subkey key nonce24) (inner-nonce nonce24) aad sealed))))

(defn seal!
  [key nonce24 aad plaintext]
  (let [r (seal key nonce24 aad plaintext)]
    (if (= :ok (:status r)) (:bytes r)
        (throw (ex-info (str "xchacha: " (name (:reason r))) r)))))

(defn open!
  [key nonce24 aad sealed]
  (let [r (open key nonce24 aad sealed)]
    (if (= :ok (:status r)) (:bytes r)
        (throw (ex-info (str "xchacha: " (name (:reason r))) r)))))

#?(:cljs
   (do
     (defn- coerce-bytes [x]
       (cond
         (instance? js/Uint8Array x) (vec (array-seq x))
         (sequential? x) (vec (map #(bit-and (int %) 0xFF) x))
         :else (throw (ex-info "xchacha: expected Uint8Array or sequential bytes" {}))))

     (defn- bytes->u8 [xs]
       (js/Uint8Array. (clojure.core/into-array (map #(bit-and (int %) 0xFF) xs))))

     (defn xchacha20poly1305
       "Noble-compatible factory: `(xchacha20poly1305 key nonce aad)` returns
       `#js {:encrypt fn :decrypt fn}` operating on `Uint8Array` values."
       [key nonce aad]
       (let [aad-bytes (when aad (coerce-bytes aad))]
         #js {:encrypt (fn [pt]
                         (bytes->u8 (seal! (coerce-bytes key) (coerce-bytes nonce)
                                           aad-bytes (coerce-bytes pt))))
              :decrypt (fn [ct]
                         (bytes->u8 (open! (coerce-bytes key) (coerce-bytes nonce)
                                           aad-bytes (coerce-bytes ct))))}))))
