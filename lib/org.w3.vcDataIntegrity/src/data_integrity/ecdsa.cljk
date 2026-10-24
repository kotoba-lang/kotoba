(ns data-integrity.ecdsa
  "The `ecdsa-jcs-2019` cryptosuite of W3C vc-di-ecdsa, P-256.

  Exists because `eddsa-jcs-2022` is Ed25519 and a great deal of the world signs
  with ECDSA P-256 — including every WebAuthn credential, and therefore every
  `did:key:zDna…` subject this workspace's apps create. Without this, such a
  credential is not merely unsupported: it is REJECTED, which is
  indistinguishable to the holder from being forged.

  Structurally identical to `data-integrity.eddsa`: same JCS transformation, same
  `hashData` = SHA-256(canonicalProofConfig) ‖ SHA-256(transformedDocument) with
  the proof configuration FIRST (§3.3.4 step 3), same multibase `z` proofValue.
  Only the signature algorithm and the key encoding differ.

  ## The two things this gets right that are easy to get wrong

  **1. proofValue is IEEE P1363, not DER.** §3.3.1 requires the signature \"per
  section 7 of RFC 4754 (sometimes referred to as the IEEE P1363 format)\",
  \"exactly 64 bytes in size for a P-256 key\" — a bare `r ‖ s`. The JVM's
  ordinary `SHA256withECDSA` emits a DER SEQUENCE instead, which is variable
  length and would be accepted by nobody. This uses
  `SHA256withECDSAinP1363Format` so the raw form is produced directly rather than
  converted, because a DER→P1363 conversion is one more place to be subtly wrong.

  **2. A P-256 `did:key` carries a COMPRESSED point.** multicodec `0x1200` is
  followed by 33 bytes: a sign byte and x. Recovering y needs a square root mod
  p, which for P-256 is a single `modPow` because p ≡ 3 (mod 4). Getting the sign
  convention backwards yields a valid-looking key that verifies nothing.

  ## Signatures here are NOT reproducible

  §3 says ECDSA signatures SHOULD use the deterministic variant, but the JVM's
  provider is randomized, so signing the same document twice gives different
  bytes. The consequence for testing is concrete and unavoidable: unlike
  `eddsa-jcs-2022`, this suite CANNOT be pinned to a fixed `proofValue`. An
  external vector can only be VERIFIED. Every signing test here is therefore a
  round-trip, and the interop assertion is verification of a signature this code
  did not produce.

  ## JVM only, for now

  The primitives are `:clj`. `:cljs` raises rather than silently doing something
  else — Node can do P-256 but the key-import path differs enough that writing it
  blind would be guessing, and this namespace loads on both hosts so the cljs
  smoke test for the rest of the library still runs.

  Reference: https://www.w3.org/TR/vc-di-ecdsa/ §3.3.1-3.3.7"
  (:require [kotoba.lang.text :as str]
            [data-integrity.bytes :as b]
            [jcs.core :as jcs]
            [multiformats.core :as mf])
  #?(:clj (:import (java.math BigInteger)
                   (java.security KeyFactory Signature)
                   (java.security.spec ECGenParameterSpec ECPoint ECPublicKeySpec
                                       PKCS8EncodedKeySpec)
                   (java.security AlgorithmParameters))))

(def proof-type "DataIntegrityProof")
(def cryptosuite-name "ecdsa-jcs-2019")

;; multicodec p256-pub, unsigned-varint 0x1200 -> 0x80 0x24.
(def p256-multicodec [0x80 0x24])
(def ^:private multibase-base58btc-prefix "z")

(defn- fail! [code msg data]
  (throw (ex-info msg (assoc data :data-integrity/error code))))

(defn unsupported-host!
  "Raised by every primitive on :cljs. Public because \"P-256 is JVM-only here\"
   is part of this namespace's stated contract, not an internal detail."
  []
  (fail! :data-integrity/host-unsupported
         (str "ecdsa-jcs-2019 primitives are implemented for :clj only. Node can "
              "do P-256, but the key-import path differs enough that writing it "
              "without testing would be guessing.")
         {}))

;; ── P-256 parameters ─────────────────────────────────────────────────────────
#?(:clj
   (do
     (def ^:private ^BigInteger p
       (BigInteger. "115792089210356248762697446949407573530086143415290314195533631308867097853951"))
     (def ^:private ^BigInteger a-coef
       (BigInteger. "115792089210356248762697446949407573530086143415290314195533631308867097853948"))
     (def ^:private ^BigInteger b-coef
       (BigInteger. "41058363725152142129326129780047268409114441015993725554835256314039467401291"))

     (defn- ec-parameters ^AlgorithmParameters []
       (doto (AlgorithmParameters/getInstance "EC")
         (.init (ECGenParameterSpec. "secp256r1"))))

     (defn- decompress-point
       "multicodec-stripped 33 bytes (sign byte ‖ x) -> ECPoint.

        y² = x³ + ax + b. p ≡ 3 (mod 4), so a square root is y = v^((p+1)/4) mod p
        and the other root is p − y; the leading byte says which one, 0x02 for even
        y and 0x03 for odd. Getting that convention backwards produces a key that
        parses and verifies nothing."
       ^ECPoint [ints]
       (when-not (= 33 (count ints))
         (fail! :data-integrity/bad-public-key
                "a compressed P-256 point is 33 bytes" {:length (count ints)}))
       (let [sign-byte (first ints)]
         (when-not (#{0x02 0x03} sign-byte)
           (fail! :data-integrity/bad-public-key
                  "a compressed point starts with 0x02 or 0x03"
                  {:sign-byte sign-byte}))
         (let [x (BigInteger. 1 (b/ints->bytes (subvec (vec ints) 1)))
               v (-> (.modPow x (BigInteger/valueOf 3) p)
                     (.add (.multiply a-coef x))
                     (.add b-coef)
                     (.mod p))
               y (.modPow v (.divide (.add p BigInteger/ONE) (BigInteger/valueOf 4)) p)
               ;; confirm it really is a root: a non-quadratic-residue x would
               ;; otherwise yield a point that is not on the curve at all.
               _ (when-not (= v (.mod (.multiply y y) p))
                   (fail! :data-integrity/bad-public-key
                          "compressed point is not on the P-256 curve" {}))
               odd? (.testBit y 0)
               want-odd? (= 0x03 sign-byte)]
           (ECPoint. x (if (= odd? want-odd?) y (.subtract p y))))))))

;; ── did:key ──────────────────────────────────────────────────────────────────

#?(:cljs (defn did-key->public-key [& _] (unsupported-host!)))

#?(:clj
   (defn did-key->public-key
     "`did:key:zDna…` (multicodec 0x1200) -> a P-256 public key object.

      Refuses an Ed25519 `did:key` explicitly rather than failing later inside the
      verifier: `z6Mk…` and `zDna…` are both valid did:keys and confusing them is a
      configuration mistake, not a cryptographic one."
     [did]
     (do
       (when-not (str/starts-with? did "did:key:z")
         (fail! :data-integrity/bad-did-key "expected a did:key:z… multibase DID" {:did did}))
       (let [ints (b/->ints (mf/base58btc-decode (subs did (count "did:key:z"))))]
         (when (= [0xed 0x01] (vec (take 2 ints)))
           (fail! :data-integrity/wrong-curve
                  (str "this is an Ed25519 did:key (multicodec 0xed01); use "
                       "data-integrity.eddsa for it")
                  {:did did}))
         (when-not (= p256-multicodec (vec (take 2 ints)))
           (fail! :data-integrity/wrong-curve
                  "expected a P-256 did:key (multicodec 0x1200)"
                  {:did did :multicodec (vec (take 2 ints))}))
         (let [point (decompress-point (vec (drop 2 ints)))
               params (.getParameterSpec (ec-parameters) java.security.spec.ECParameterSpec)]
           (.generatePublic (KeyFactory/getInstance "EC")
                            (ECPublicKeySpec. point params)))))))

;; ── §3.3.3 / §3.3.5 / §3.3.4 ─────────────────────────────────────────────────

(defn- assert-suite! [proof-options]
  (when-not (= proof-type (get proof-options "type"))
    (fail! :data-integrity/bad-proof-type (str "proof type must be " proof-type)
           {:got (get proof-options "type")}))
  (when-not (= cryptosuite-name (get proof-options "cryptosuite"))
    (fail! :data-integrity/bad-cryptosuite
           (str "cryptosuite must be " cryptosuite-name)
           {:got (get proof-options "cryptosuite")})))

(defn transform
  ;; the opts-ignoring arity lets core/issue call every suite identically
  ([unsecured-document proof-options] (transform unsecured-document proof-options nil))
  ([unsecured-document proof-options _opts]
   (assert-suite! proof-options)
   (jcs/canonicalize-bytes unsecured-document)))

(defn proof-configuration
  ([proof-options] (proof-configuration proof-options nil))
  ([proof-options _opts]
   (assert-suite! proof-options)
   (jcs/canonicalize-bytes proof-options)))

(defn hash-data
  "§3.3.4. proofConfigHash FIRST, then transformedDocumentHash — the same order
   `eddsa-jcs-2022` uses, and the same trap if reversed. P-256 means SHA-256
   (§3.3.4: \"for curve P-256 one uses SHA-256\")."
  [transformed-bytes proof-config-bytes]
  (b/concat-bytes (mf/sha256 proof-config-bytes) (mf/sha256 transformed-bytes)))

;; ── proofValue ───────────────────────────────────────────────────────────────

(defn encode-proof-value [sig]
  (when-not (= 64 (b/byte-count sig))
    (fail! :data-integrity/bad-signature-length
           (str "a P-256 signature in IEEE P1363 form is exactly 64 bytes; got "
                (b/byte-count sig) " — a DER-encoded signature is the usual cause")
           {:length (b/byte-count sig)}))
  (str multibase-base58btc-prefix (mf/base58btc sig)))

(defn decode-proof-value [proof-value]
  (when-not (string? proof-value)
    (fail! :data-integrity/missing-proof-value "proof is missing `proofValue`" {}))
  (when-not (str/starts-with? proof-value multibase-base58btc-prefix)
    (fail! :data-integrity/bad-multibase
           "proofValue must be multibase base58-btc (prefix `z`)"
           {:prefix (when (seq proof-value) (subs proof-value 0 1))}))
  (let [sig (b/ints->bytes (b/->ints (mf/base58btc-decode (subs proof-value 1))))]
    (when-not (= 64 (b/byte-count sig))
      (fail! :data-integrity/bad-signature-length
             "a P-256 signature in IEEE P1363 form is exactly 64 bytes"
             {:length (b/byte-count sig)}))
    sig))

;; ── §3.3.6 / §3.3.7 ──────────────────────────────────────────────────────────

#?(:cljs (defn sign-hash-data [& _] (unsupported-host!)))

#?(:clj
   (defn sign-hash-data
     "§3.3.6. `private-key` is a `java.security.PrivateKey`, or PKCS#8 bytes.

      NOT reproducible: the JVM provider is randomized, so the same document signs
      to different bytes each time. §3 only SHOULDs determinism."
     [private-key hash-bytes]
     (let [key (if (instance? java.security.PrivateKey private-key)
                 private-key
                 (.generatePrivate (KeyFactory/getInstance "EC")
                                   (PKCS8EncodedKeySpec.
                                    (b/ints->bytes (b/->ints private-key)))))
           s (doto (Signature/getInstance "SHA256withECDSAinP1363Format")
               (.initSign key))]
       (.update s ^bytes hash-bytes)
       (let [sig (.sign s)]
         (when-not (= 64 (b/byte-count sig))
           (fail! :data-integrity/bad-signature-length
                  "signer did not return a 64-byte P1363 signature"
                  {:length (b/byte-count sig)}))
         sig))))

#?(:cljs (defn verify-hash-data [& _] (unsupported-host!)))

#?(:clj
   (defn verify-hash-data
     "§3.3.7. Returns a boolean; a wrong signature is `false`, not an exception."
     [public-key hash-bytes sig]
     (let [key (if (instance? java.security.PublicKey public-key)
                 public-key
                 (did-key->public-key (str public-key)))]
       (boolean
        (try
          (let [v (doto (Signature/getInstance "SHA256withECDSAinP1363Format")
                    (.initVerify key))]
            (.update v ^bytes hash-bytes)
            (.verify v ^bytes sig))
          (catch Exception _ false))))))

(def suite
  "The `ecdsa-jcs-2019` cryptosuite as data, shaped like `data-integrity.eddsa/suite`
   so `data-integrity.core/issue`/`verify` take it unchanged."
  {:type proof-type
   :cryptosuite cryptosuite-name
   :transform transform
   :proof-configuration proof-configuration
   :hash hash-data
   :sign sign-hash-data
   :verify verify-hash-data
   :encode-proof-value encode-proof-value
   :decode-proof-value decode-proof-value})
