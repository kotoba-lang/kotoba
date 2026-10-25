(ns hpke.kdf
  "HKDF ([RFC 5869](https://www.rfc-editor.org/rfc/rfc5869)) and the labeled
  Extract/Expand that [RFC 9180](https://www.rfc-editor.org/rfc/rfc9180) §4
  builds on it, over all three of the RFC's KDFs.

  A KDF is a value: `{:kdf-id … :nh … :hmac …}`. There is no branch on the
  identifier anywhere below, which is the point — HKDF-SHA384 and
  HKDF-SHA512 are the same construction with a different MAC and a different
  output length, and writing them as a branch would be writing the
  construction three times.

  ## Why not kotoba-lang/crypto's hkdf

  That one **hardcodes a zero salt** — it is `HMAC(zeros, ikm)`, which is
  HKDF's default when no salt is given, not HKDF. RFC 9180 passes a real salt
  in the key schedule (`LabeledExtract(shared_secret, \"secret\", psk)`), so a
  fixed-salt Extract computes a different function. Its default digest is also
  a JVM `MessageDigest`, which a portable file cannot use.

  The MACs here are `kotoba-lang/org-nist-sha2` — actual implementations on
  both runtimes rather than a seam."
  (:require [sha2.core :as sha2]
            [sha2.sha512 :as sha512]))

(def hkdf-sha256 {:kdf-id 0x0001 :nh 32 :hmac sha2/hmac-sha256})
(def hkdf-sha384 {:kdf-id 0x0002 :nh 48 :hmac sha512/hmac-sha384})
(def hkdf-sha512 {:kdf-id 0x0003 :nh 64 :hmac sha512/hmac-sha512})

(def kdfs
  "The three RFC 9180 names, by identifier. All three run."
  {0x0001 hkdf-sha256 0x0002 hkdf-sha384 0x0003 hkdf-sha512})

(defn- ->ints [x] (mapv #(bit-and (int %) 0xFF) (seq x)))

(defn extract
  "HKDF-Extract: `HMAC(salt, ikm)`.

  An empty salt means a string of `Nh` zero bytes, per RFC 5869 §2.2 — which
  is not the same as an empty HMAC key, and getting it wrong changes every
  derived byte. `Nh` follows the KDF, so the zero salt is 32, 48 or 64 bytes
  and never one length borrowed from another suite."
  [kdf salt ikm]
  (->ints ((:hmac kdf)
           (if (seq salt) (->ints salt) (vec (repeat (:nh kdf) 0)))
           (->ints ikm))))

(defn expand
  "HKDF-Expand to `length` bytes.

  `T(i) = HMAC(prk, T(i-1) || info || i)` with a ONE-BYTE counter, so the
  maximum output is `255 * Nh`. Refusing past that rather than silently
  wrapping the counter is the difference between a short read and two
  different callers deriving the same key."
  [kdf prk info length]
  (let [nh (:nh kdf) hmac (:hmac kdf)]
    (if (> length (* 255 nh))
      {:status :error :reason :expand-length-too-large :length length :nh nh}
      (let [prk (->ints prk) info (->ints info)
            n (quot (+ length (dec nh)) nh)]
        {:status :ok
         :bytes (vec (take length
                           (mapcat identity
                                   (reductions
                                    (fn [t i] (->ints (hmac prk (concat t info [i]))))
                                    (->ints (hmac prk (concat info [1])))
                                    (range 2 (inc n))))))}))))

(defn expand!
  [kdf prk info length]
  (let [r (expand kdf prk info length)]
    (if (= :ok (:status r)) (:bytes r)
        (throw (ex-info (str "hkdf: " (name (:reason r))) r)))))

;; ── RFC 9180 §4, the labeled forms ───────────────────────────────────────────

(def ^:private version-label
  "\"HPKE-v1\". Domain separation from any other protocol that derives keys
  with HKDF over the same secret."
  [0x48 0x50 0x4B 0x45 0x2D 0x76 0x31])

(defn ascii
  "An ASCII label as bytes.

  Not `(map int s)`: on the JVM that is code points and under ClojureScript a
  vector of zeros, so every label would collide and the domain separation this
  file exists for would be gone."
  [s]
  #?(:clj (mapv #(bit-and % 0xFF) (.getBytes ^String s "US-ASCII"))
     :cljs (mapv #(.charCodeAt s %) (range (count s)))))

(defn labeled-extract
  "RFC 9180 §4: `Extract(salt, \"HPKE-v1\" || suite_id || label || ikm)`."
  [kdf suite-id salt label ikm]
  (extract kdf salt (vec (concat version-label suite-id (ascii label) (->ints ikm)))))

(defn labeled-expand
  "RFC 9180 §4:
  `Expand(prk, I2OSP(L,2) || \"HPKE-v1\" || suite_id || label || info, L)`.

  The length prefix is inside the info, not just an argument — two calls that
  differ only in output length must produce unrelated bytes."
  [kdf suite-id prk label info length]
  (expand! kdf prk
           (vec (concat [(bit-and (quot length 256) 0xFF) (bit-and length 0xFF)]
                        version-label suite-id (ascii label) (->ints info)))
           length))
