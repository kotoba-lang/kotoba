;; etzhayyim.kotoba.crypto — XChaCha20-Poly1305 AEAD (root-side reference impl).
;;
;; Increment #2 (ADR-2605181100): the religious-corp confidential-record wire
;; format is a FROZEN constitutional artifact; kotoba-crypto / kotoba-signal will
;; later re-implement it and a bit-identical test-vector suite is the Phase-5
;; acceptance gate. This is the root-side reference the gate verifies against —
;; it lives in root (70-tools/src), NOT in the kotoba subrepo.
;;
;; CONSTRUCTION (XChaCha20-Poly1305, draft-irtf-cfrg-xchacha):
;;   subkey   = HChaCha20(key, nonce[0..16))
;;   n12      = 0x00000000 || nonce[16..24)          ; 12-byte IETF nonce
;;   AEAD     = ChaCha20-Poly1305(subkey, n12, aad, plaintext)   ; RFC 8439
;;
;; HChaCha20 reuses the exact ChaCha20 20-round permutation; only the IETF
;; ChaCha20-Poly1305 step is delegated to the JDK (javax.crypto, Java 11+).
;;
;; BIT-IDENTICAL VALIDATION (see test_crypto):
;;   - ChaCha20 permutation  vs RFC 8439 §2.3.2
;;   - HChaCha20             vs draft-irtf-cfrg-xchacha-00 §2.2.1
;;   - ChaCha20-Poly1305     vs RFC 8439 §2.8.2

(ns etzhayyim.kotoba.crypto
  #?(:clj (:import (javax.crypto Cipher)
                   (javax.crypto.spec SecretKeySpec IvParameterSpec))))

;; ── u32 helpers ──
(defn- m32 ^long [^long x] (bit-and x 0xFFFFFFFF))
(defn- add32 ^long [^long a ^long b] (m32 (+ a b)))
(defn- rotl32 ^long [^long x ^long n]
  (m32 (bit-or (bit-shift-left x n) (unsigned-bit-shift-right (m32 x) (- 32 n)))))

(def ^:private chacha-constants
  ;; "expand 32-byte k" as four little-endian u32 words
  [0x61707865 0x3320646e 0x79622d32 0x6b206574])

(defn- le32 ^long [^bytes b ^long off]
  (bit-or (bit-and (aget b off) 0xff)
          (bit-shift-left (bit-and (aget b (+ off 1)) 0xff) 8)
          (bit-shift-left (bit-and (aget b (+ off 2)) 0xff) 16)
          (bit-shift-left (bit-and (aget b (+ off 3)) 0xff) 24)))

(defn- words->le-bytes ^bytes [words]
  (let [out (byte-array (* 4 (count words)))]
    (doseq [[i w] (map-indexed vector words)]
      (let [o (* 4 i)]
        (aset out o (unchecked-byte (bit-and w 0xff)))
        (aset out (+ o 1) (unchecked-byte (bit-and (unsigned-bit-shift-right w 8) 0xff)))
        (aset out (+ o 2) (unchecked-byte (bit-and (unsigned-bit-shift-right w 16) 0xff)))
        (aset out (+ o 3) (unchecked-byte (bit-and (unsigned-bit-shift-right w 24) 0xff)))))
    out))

(defn- quarter-round! [^longs s a b c d]
  (aset s a (add32 (aget s a) (aget s b)))
  (aset s d (rotl32 (bit-xor (aget s d) (aget s a)) 16))
  (aset s c (add32 (aget s c) (aget s d)))
  (aset s b (rotl32 (bit-xor (aget s b) (aget s c)) 12))
  (aset s a (add32 (aget s a) (aget s b)))
  (aset s d (rotl32 (bit-xor (aget s d) (aget s a)) 8))
  (aset s c (add32 (aget s c) (aget s d)))
  (aset s b (rotl32 (bit-xor (aget s b) (aget s c)) 7)))

(defn- permute!
  "Run the ChaCha 20-round (10 double-round) permutation in place on a 16-long array."
  [^longs s]
  (dotimes [_ 10]
    ;; column rounds
    (quarter-round! s 0 4 8 12)
    (quarter-round! s 1 5 9 13)
    (quarter-round! s 2 6 10 14)
    (quarter-round! s 3 7 11 15)
    ;; diagonal rounds
    (quarter-round! s 0 5 10 15)
    (quarter-round! s 1 6 11 12)
    (quarter-round! s 2 7 8 13)
    (quarter-round! s 3 4 9 14))
  s)

(defn hchacha20
  "HChaCha20 subkey derivation. `key` = 32 bytes, `nonce16` = 16 bytes.
   Returns a 32-byte subkey (the permuted words 0-3 ++ 12-15, no state-add)."
  ^bytes [^bytes key ^bytes nonce16]
  (let [s (long-array 16)]
    (dotimes [i 4] (aset s i (long (nth chacha-constants i))))
    (dotimes [i 8] (aset s (+ 4 i) (le32 key (* 4 i))))
    (dotimes [i 4] (aset s (+ 12 i) (le32 nonce16 (* 4 i))))
    (permute! s)
    (words->le-bytes (map #(aget s %) [0 1 2 3 12 13 14 15]))))

;; Exposed for KAT validation of the raw permutation (RFC 8439 §2.3.2).
(defn ^:no-doc chacha-permuted-state
  "Set up the ChaCha state (RFC 8439 layout: counter in word 12, 12-byte nonce in
   13-15) and return the 16 words AFTER 20 rounds, BEFORE the final state-add."
  [^bytes key ^long counter ^bytes nonce12]
  (let [s (long-array 16)]
    (dotimes [i 4] (aset s i (long (nth chacha-constants i))))
    (dotimes [i 8] (aset s (+ 4 i) (le32 key (* 4 i))))
    (aset s 12 (m32 counter))
    (dotimes [i 3] (aset s (+ 13 i) (le32 nonce12 (* 4 i))))
    (permute! s)
    (mapv #(aget s %) (range 16))))

;; ── IETF ChaCha20-Poly1305 via the JDK ──
(defn- chacha20-poly1305
  [mode ^bytes subkey ^bytes nonce12 ^bytes aad ^bytes input]
  #?(:clj (let [c (Cipher/getInstance "ChaCha20-Poly1305")
                k (SecretKeySpec. subkey "ChaCha20")
                iv (IvParameterSpec. nonce12)]
            (.init c (int mode) k iv)
            (when (and aad (pos? (alength aad))) (.updateAAD c aad))
            (.doFinal c input))
     :cljs (throw (ex-info "cljs crypto not wired (root engine runs on bb/JVM)" {}))))

(defn xchacha20-poly1305-encrypt
  "Encrypt with XChaCha20-Poly1305. key=32B, nonce24=24B, aad may be nil.
   Returns ciphertext||tag (tag = last 16 bytes)."
  ^bytes [^bytes key ^bytes nonce24 ^bytes aad ^bytes plaintext]
  (let [subkey (hchacha20 key (java.util.Arrays/copyOfRange nonce24 0 16))
        n12 (byte-array 12)]
    (System/arraycopy nonce24 16 n12 4 8) ; 0x00000000 || nonce[16..24)
    #?(:clj (chacha20-poly1305 Cipher/ENCRYPT_MODE subkey n12 aad plaintext)
       :cljs nil)))

(defn xchacha20-poly1305-decrypt
  "Decrypt+verify. `ct+tag` = ciphertext||tag (16-byte tag). Throws on bad tag."
  ^bytes [^bytes key ^bytes nonce24 ^bytes aad ^bytes ct+tag]
  (let [subkey (hchacha20 key (java.util.Arrays/copyOfRange nonce24 0 16))
        n12 (byte-array 12)]
    (System/arraycopy nonce24 16 n12 4 8)
    #?(:clj (chacha20-poly1305 Cipher/DECRYPT_MODE subkey n12 aad ct+tag)
       :cljs nil)))

(def alg-id "xchacha20poly1305")
