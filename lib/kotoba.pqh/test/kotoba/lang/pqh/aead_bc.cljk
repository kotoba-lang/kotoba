(ns kotoba.lang.pqh.aead-bc
  "JVM BouncyCastle host impl of kotoba.lang.pqh.crypto/IAead -- the raw IETF
   ChaCha20-Poly1305 primitive (32-byte key, 12-byte nonce, 128-bit tag).

   Lives under test/ (not src/) so the lib core stays vendor-free per
   ADR-2607012200: the pure core declares the IAead seam, the host supplies a
   vetted impl. Consumers bring an equivalent impl on their own classpath.

   Correctly JVM-only .clj (not .cljc): directly imports org.bouncycastle.*
   to implement the raw primitive. BouncyCastle is a :test-scoped dep
   (deps.edn `:test` alias `org.bouncycastle/bcprov-jdk18on`, not `:deps`),
   so this is a test fixture, not a production seam impl -- a real cljs
   host impl would use @noble/ciphers instead (see crypto.cljc)."
  (:require [kotoba.lang.pqh.crypto :as crypto])
  (:import (org.bouncycastle.crypto.modes ChaCha20Poly1305)
           (org.bouncycastle.crypto.params AEADParameters KeyParameter)
           (org.bouncycastle.crypto InvalidCipherTextException)
           (java.util Arrays)))

(defn bc-aead
  "Returns an IAead backed by BouncyCastle's RFC 8439 ChaCha20-Poly1305."
  []
  (reify crypto/IAead
    (-aead12-encrypt [_ key nonce12 aad plaintext]
      (let [cipher (ChaCha20Poly1305.)
            params (if aad
                     (AEADParameters. (KeyParameter. ^bytes key) 128 ^bytes nonce12 ^bytes aad)
                     (AEADParameters. (KeyParameter. ^bytes key) 128 ^bytes nonce12))]
        (.init cipher true params)
        (let [out (byte-array (.getOutputSize cipher (alength ^bytes plaintext)))
              len1 (.processBytes cipher ^bytes plaintext 0 (alength ^bytes plaintext) out 0)
              len2 (.doFinal cipher out len1)]
          (Arrays/copyOf out (+ len1 len2)))))
    (-aead12-decrypt [_ key nonce12 aad ciphertext]
      (let [cipher (ChaCha20Poly1305.)
            params (if aad
                     (AEADParameters. (KeyParameter. ^bytes key) 128 ^bytes nonce12 ^bytes aad)
                     (AEADParameters. (KeyParameter. ^bytes key) 128 ^bytes nonce12))]
        (.init cipher false params)
        (let [out (byte-array (.getOutputSize cipher (alength ^bytes ciphertext)))]
          (try
            (let [len1 (.processBytes cipher ^bytes ciphertext 0 (alength ^bytes ciphertext) out 0)
                  len2 (.doFinal cipher out len1)]
              (Arrays/copyOf out (+ len1 len2)))
            (catch InvalidCipherTextException e
              (throw (ex-info "[kotoba.lang.pqh/crypto] AEAD authentication failed" {} e)))))))))
