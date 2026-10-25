(ns wallet.keystore
  "Local encrypted keystore for a wallet's private key material, shaped
  around kotoba-lang/crypto's `IAEAD` data contract (encrypt/decrypt return
  ciphertext+tag maps; the cipher itself is injectable). Ships a real
  AES-256-GCM `IAEAD` for the JVM (kotoba.lang.crypto's own `mock-aead` is
  explicitly test-only) plus PBKDF2-HMAC-SHA256 passphrase-to-key
  stretching. Private keys are never logged."
  (:require [kotoba.lang.crypto :as kc])
  #?(:clj (:import (javax.crypto Cipher Mac)
                    (javax.crypto.spec SecretKeySpec GCMParameterSpec)
                    (java.security SecureRandom))))

(defn random-bytes ^bytes [^long n]
  #?(:clj (let [b (byte-array n)] (.nextBytes (SecureRandom.) b) b)
     :cljs (throw (js/Error. "wallet.keystore: not yet implemented for cljs"))))

(defn- hmac-sha256 ^bytes [^bytes key ^bytes data]
  #?(:clj (let [mac (Mac/getInstance "HmacSHA256")]
            (.init mac (SecretKeySpec. key "HmacSHA256"))
            (.doFinal mac data))
     :cljs (throw (js/Error. "wallet.keystore: not yet implemented for cljs"))))

(defn pbkdf2-hmac-sha256
  "Stretch `passphrase` (UTF-8) + `salt` into a `dklen`-byte key (PBKDF2,
  RFC 8018) for the passphrase that protects a local keystore."
  ^bytes [^String passphrase ^bytes salt ^long iterations ^long dklen]
  #?(:clj
     (let [password (.getBytes passphrase "UTF-8")
           hlen 32
           blocks (long (Math/ceil (/ dklen (double hlen))))
           u1 (fn [^long i] (hmac-sha256 password (byte-array (concat salt [(unchecked-byte (bit-shift-right i 24))
                                                                             (unchecked-byte (bit-shift-right i 16))
                                                                             (unchecked-byte (bit-shift-right i 8))
                                                                             (unchecked-byte i)]))))
           f (fn [^long i] (loop [j 1 u (u1 i) acc u]
                             (if (= j iterations) acc
                                 (let [u' (hmac-sha256 password u)]
                                   (recur (inc j) u' (byte-array (map bit-xor acc u')))))))
           out (byte-array (* blocks hlen))]
       (dotimes [b blocks] (System/arraycopy (f (inc b)) 0 out (* b hlen) hlen))
       (java.util.Arrays/copyOfRange out 0 dklen))
     :cljs (throw (js/Error. "wallet.keystore: not yet implemented for cljs"))))

(def aes-gcm-aead
  "A real AES-256-GCM `kotoba.lang.crypto/IAEAD` for the JVM. `key` must be
  32 bytes; `nonce` should be 12 bytes and MUST be unique per key (use
  `random-bytes 12` per encryption)."
  (reify kc/IAEAD
    (encrypt [_ key nonce plaintext aad]
      #?(:clj
         (let [cipher (Cipher/getInstance "AES/GCM/NoPadding")]
           (.init cipher Cipher/ENCRYPT_MODE (SecretKeySpec. key "AES") (GCMParameterSpec. 128 nonce))
           (when (seq aad) (.updateAAD cipher ^bytes aad))
           (let [out (.doFinal cipher plaintext)
                 tag-len 16
                 n (alength out)]
             {:ciphertext (java.util.Arrays/copyOfRange out 0 (- n tag-len))
              :tag (java.util.Arrays/copyOfRange out (- n tag-len) n)}))
         :cljs (throw (js/Error. "wallet.keystore: not yet implemented for cljs"))))
    (decrypt [_ key nonce ciphertext tag aad]
      #?(:clj
         (let [cipher (Cipher/getInstance "AES/GCM/NoPadding")]
           (.init cipher Cipher/DECRYPT_MODE (SecretKeySpec. key "AES") (GCMParameterSpec. 128 nonce))
           (when (seq aad) (.updateAAD cipher ^bytes aad))
           (.doFinal cipher (byte-array (concat ciphertext tag))))
         :cljs (throw (js/Error. "wallet.keystore: not yet implemented for cljs"))))))

(defn encrypt-keystore
  "Encrypt `private-key` under `passphrase`. Returns a persistable map
  {:salt :nonce :ciphertext :tag :kdf-iterations} (all byte arrays except
  :kdf-iterations)."
  ([private-key passphrase] (encrypt-keystore private-key passphrase 200000))
  ([private-key passphrase kdf-iterations]
   #?(:clj
      (let [salt (random-bytes 16)
            nonce (random-bytes 12)
            key (pbkdf2-hmac-sha256 passphrase salt kdf-iterations 32)
            {:keys [ciphertext tag]} (kc/encrypt aes-gcm-aead key nonce private-key (byte-array 0))]
        {:salt salt :nonce nonce :ciphertext ciphertext :tag tag :kdf-iterations kdf-iterations})
      :cljs (throw (js/Error. "wallet.keystore: not yet implemented for cljs")))))

(defn decrypt-keystore
  "Inverse of `encrypt-keystore`. Throws (AEAD auth failure) on a wrong
  passphrase or tampered ciphertext."
  ^bytes [{:keys [salt nonce ciphertext tag kdf-iterations]} ^String passphrase]
  #?(:clj
     (let [key (pbkdf2-hmac-sha256 passphrase salt kdf-iterations 32)]
       (kc/decrypt aes-gcm-aead key nonce ciphertext tag (byte-array 0)))
     :cljs (throw (js/Error. "wallet.keystore: not yet implemented for cljs"))))
