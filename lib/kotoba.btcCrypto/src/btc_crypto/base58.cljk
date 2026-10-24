(ns btc-crypto.base58
  "Base58 and Base58Check (Bitcoin's WIF/legacy-address encoding). BigInteger-
  based, mirroring eth-crypto's style of using only java.math.BigInteger for
  bignum arithmetic (no third-party deps).

  PORTABILITY: :clj-only (wrapped #?(:clj (do ...)) with throwing :cljs
  stubs of the same names, matching eth-crypto.core's precedent) — needs
  java.math.BigInteger arbitrary-precision arithmetic."
  (:require [kotoba.lang.crypto :as kc])
  #?(:clj (:import (java.math BigInteger))))

#?(:clj
(do

(def ^:private ALPHABET "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
(def ^:private ALPHABET-IDX (into {} (map-indexed (fn [i c] [c i]) ALPHABET)))
(def ^:private BASE (BigInteger/valueOf 58))

(defn- leading-zero-count ^long [^bytes b]
  (loop [i 0] (if (and (< i (alength b)) (zero? (aget b i))) (recur (inc i)) i)))

(defn encode
  "Base58-encode a byte array (leading 0x00 bytes become leading '1's)."
  ^String [^bytes b]
  (let [zeros (leading-zero-count b)
        n (if (zero? (alength b)) BigInteger/ZERO (BigInteger. 1 b))
        sb (StringBuilder.)]
    (loop [^BigInteger n n]
      (when (pos? (.signum n))
        (let [[q r] [(.divide n BASE) (.mod n BASE)]]
          (.append sb (.charAt ALPHABET (.intValue ^BigInteger r)))
          (recur q))))
    (dotimes [_ zeros] (.append sb \1))
    (.toString (.reverse sb))))

(defn decode
  "Decode a Base58 string back to a byte array (inverse of `encode`)."
  ^bytes [^String s]
  (let [zeros (loop [i 0] (if (and (< i (count s)) (= (.charAt s i) \1)) (recur (inc i)) i))
        n (reduce (fn [^BigInteger acc c]
                     (let [d (get ALPHABET-IDX c)]
                       (when (nil? d) (throw (ex-info "base58: invalid character" {:char c})))
                       (.add (.multiply acc BASE) (BigInteger/valueOf (long d)))))
                   BigInteger/ZERO
                   (drop zeros s))
        body (if (zero? (.signum ^BigInteger n))
               (byte-array 0)
               (let [^bytes raw (.toByteArray ^BigInteger n)]
                 (if (and (> (alength raw) 1) (zero? (aget raw 0)))
                   (java.util.Arrays/copyOfRange raw 1 (alength raw)) ; strip BigInteger sign byte
                   raw)))
        out (byte-array (+ zeros (alength body)))]
    (System/arraycopy body 0 out zeros (alength body))
    out))

(defn- sha256d ^bytes [^bytes data] (kc/hash :sha256 (kc/hash :sha256 data)))

(defn encode-check
  "Base58Check-encode `payload` (already including any version-byte prefix):
  append a 4-byte checksum = first 4 bytes of SHA256(SHA256(payload))."
  ^String [^bytes payload]
  (let [checksum (java.util.Arrays/copyOfRange (sha256d payload) 0 4)
        full (byte-array (+ (alength payload) 4))]
    (System/arraycopy payload 0 full 0 (alength payload))
    (System/arraycopy checksum 0 full (alength payload) 4)
    (encode full)))

(defn decode-check
  "Decode + verify a Base58Check string. Returns the payload (without the
  4-byte checksum) or throws if the checksum does not match."
  ^bytes [^String s]
  (let [full (decode s)
        n (alength full)]
    (when (< n 4) (throw (ex-info "base58check: too short" {:s s})))
    (let [payload (java.util.Arrays/copyOfRange full 0 (- n 4))
          given (java.util.Arrays/copyOfRange full (- n 4) n)
          want (java.util.Arrays/copyOfRange (sha256d payload) 0 4)]
      (when-not (java.util.Arrays/equals ^bytes given ^bytes want)
        (throw (ex-info "base58check: checksum mismatch" {:s s})))
      payload)))

) ;; end do
:cljs
(do
  (defn encode [& _] (throw (ex-info "btc-crypto.base58/encode is :clj-only (java.math.BigInteger)" {})))
  (defn decode [& _] (throw (ex-info "btc-crypto.base58/decode is :clj-only (java.math.BigInteger)" {})))
  (defn encode-check [& _] (throw (ex-info "btc-crypto.base58/encode-check is :clj-only (java.math.BigInteger)" {})))
  (defn decode-check [& _] (throw (ex-info "btc-crypto.base58/decode-check is :clj-only (java.math.BigInteger)" {})))))
