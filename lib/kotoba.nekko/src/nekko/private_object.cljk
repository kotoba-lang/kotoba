(ns nekko.private-object
  "kotoba-rad R2: encrypt a git object's bytes under a repo epoch key so the
   REPLICATED blob is ciphertext. Per ADR-2606280300's Security model:

     replication key         = ciphertext-cid   (what peers store/route)
     verification metadata   = plaintext-cid    (the object's real git oid,
                                                  authority-scoped)

   A private object is {:epoch :plaintext-cid :iv :ct}: AES-256-GCM of the
   object bytes under the epoch key, plus the plaintext CID so a decrypting
   holder can verify the recovered bytes hash back to the claimed object
   identity (integrity + wrong-key detection beyond the GCM tag). The
   ciphertext's own CID is what a private replica addresses; a peer without
   an epoch-key grant (nekko.recipient-grant) can replicate the
   ciphertext but never read it.

   Deliberately NARROW: this seals/opens ONE object's bytes. Composing it
   over a whole kotoba-git repo (which objects to seal, how commit trees
   reference ciphertext CIDs) is the R2 storage-layer wiring above this;
   this namespace is the crypto envelope only, so it stays testable and
   host-portable (JVM + nbb, same AES-256-GCM as recipient-grant)."
  (:require [nekko.bytes :as b]
            #?(:cljs ["crypto" :as ncrypto])))

(defn- cidish
  "A stable content id for `bytes` — sha-256 hex, prefixed so it never reads
   as a real multibase/multihash CID (this is R2's verification-metadata id,
   not a kotoba-git object CID; kotoba-git owns those)."
  [bytes]
  (str "r2sha256:" (b/hexify (b/sha256 bytes))))

(defn- gcm-encrypt [key-hex iv plain]
  #?(:clj
     (let [c (doto (javax.crypto.Cipher/getInstance "AES/GCM/NoPadding")
               (.init javax.crypto.Cipher/ENCRYPT_MODE
                      (javax.crypto.spec.SecretKeySpec. (b/->ba (b/unhex key-hex)) "AES")
                      (javax.crypto.spec.GCMParameterSpec. 128 (b/->ba iv))))]
       (b/hexify (.doFinal c (b/->ba plain))))
     :cljs
     (let [c (ncrypto/createCipheriv "aes-256-gcm" (js/Buffer.from (b/unhex key-hex))
                                     (js/Buffer.from iv))
           body (js/Buffer.concat #js[(.update c (js/Buffer.from plain)) (.final c)])]
       (b/hexify (js/Buffer.concat #js[body (.getAuthTag c)])))))

(defn- gcm-decrypt [key-hex iv-hex ct-hex]
  (let [ct (b/unhex ct-hex) n (b/blen ct)
        body (b/slice ct 0 (- n 16)) tag (b/slice ct (- n 16) n)]
    #?(:clj
       (let [d (doto (javax.crypto.Cipher/getInstance "AES/GCM/NoPadding")
                 (.init javax.crypto.Cipher/DECRYPT_MODE
                        (javax.crypto.spec.SecretKeySpec. (b/->ba (b/unhex key-hex)) "AES")
                        (javax.crypto.spec.GCMParameterSpec. 128 (b/->ba (b/unhex iv-hex)))))]
         (.doFinal d (b/->ba ct)))
       :cljs
       (let [d (ncrypto/createDecipheriv "aes-256-gcm" (js/Buffer.from (b/unhex key-hex))
                                         (js/Buffer.from (b/unhex iv-hex)))]
         (.setAuthTag d (js/Buffer.from tag))
         (js/Uint8Array. (js/Buffer.concat #js[(.update d (js/Buffer.from body)) (.final d)]))))))

(defn seal
  "Encrypt object `bytes` under `epoch-key-hex` at `epoch`. Returns
   {:epoch :plaintext-cid :iv :ct} — :ct is ciphertext||tag (hex). A random
   96-bit iv per object (never reused under one key)."
  [epoch epoch-key-hex bytes]
  (let [iv (b/random-bytes 12)]
    {:epoch epoch
     :plaintext-cid (cidish bytes)
     :iv (b/hexify iv)
     :ct (gcm-encrypt epoch-key-hex iv bytes)}))

(defn open
  "Decrypt a sealed object with `epoch-key-hex` -> the original bytes, AND
   verify they hash back to :plaintext-cid. Throws on a bad tag (wrong key /
   tampered ct) or a plaintext-cid mismatch."
  [sealed epoch-key-hex]
  (let [plain (gcm-decrypt epoch-key-hex (:iv sealed) (:ct sealed))]
    (when-not (= (cidish plain) (:plaintext-cid sealed))
      (throw (ex-info "private-object: recovered bytes do not match plaintext-cid"
                      {:expected (:plaintext-cid sealed)})))
    plain))

(defn ciphertext-cid
  "The replication id of a sealed object: the CID of its ciphertext (what a
   private replica addresses/routes on, blind to the plaintext)."
  [sealed]
  (str "r2ct:" (b/hexify (b/sha256 (b/unhex (:ct sealed))))))
