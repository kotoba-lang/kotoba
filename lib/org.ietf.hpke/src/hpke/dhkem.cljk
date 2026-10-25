(ns hpke.dhkem
  "The five DHKEMs of [RFC 9180](https://www.rfc-editor.org/rfc/rfc9180) §4.1
  and §7.1 — X25519, X448, P-256, P-384 and P-521.

  A KEM built from a Diffie-Hellman: the sender makes an ephemeral key,
  multiplies it with the recipient's public key, and derives a shared secret
  from that product **together with both public keys**. Binding the context is
  what stops a sender's encapsulation being replayed toward a different
  recipient.

  ## A KEM is a value

  `encap`, `decap`, `auth-encap` and `auth-decap` take one and never branch on
  which it is. What differs between the five is confined to the map: the
  identifier, four lengths, the KDF, and two functions — `dh` and `pk-of`.

  Two things do differ in kind, and both are in `derive-key-pair`:

  - **the NIST curves need rejection sampling.** A random 32-byte string is a
    valid X25519 scalar because X25519 clamps; on P-256 it is a valid scalar
    only if it lands below the group order, so RFC 9180 §7.1.3 draws
    candidates until one does. This is why the specification's text for those
    curves looks so much more complicated than for the Montgomery ones.
  - **P-521's bitmask is `0x01`, not `0xFF`.** Its order is 521 bits inside 66
    bytes, so all but one bit of the leading byte must be cleared or every
    candidate is far above the order and the loop runs out of counter.

  ## The KDF here is the KEM's, not the ciphersuite's

  RFC 9180 §7.1.3 is explicit: every `LabeledExtract` and `LabeledExpand`
  inside a DHKEM uses **the DHKEM's own KDF**. A suite may pair
  DHKEM(P-256, HKDF-SHA256) with HKDF-SHA512 — Appendix A.4 does — and then
  the KEM still derives with SHA-256 while the key schedule derives with
  SHA-512. Reading `(:kdf suite)` here instead of `(:kdf kem)` produces a
  library that is correct for four of the RFC's appendices and wrong for that
  one."
  (:require [ecc.bignum :as bn]
            [ecc.curve :as curve]
            [ecc.ecdh :as ecdh]
            [hpke.kdf :as kdf]
            [x25519.core :as x25519]
            [x448.core :as x448]))

(defn- suite-id-for [kem-id]
  (vec (concat (kdf/ascii "KEM") [(quot kem-id 256) (mod kem-id 256)])))

;; ── the Montgomery KEMs ──────────────────────────────────────────────────────

(defn- montgomery-kem
  [nm kem-id nsecret n the-kdf dh-fn pk-fn contributory-fn]
  {:name nm :kem-id kem-id :suite-id (suite-id-for kem-id)
   :nsecret nsecret :nsk n :npk n :nenc n
   :kdf the-kdf :montgomery? true
   :dh (fn [sk pk]
         (let [r (dh-fn sk pk)]
           (cond
             (not= :ok (:status r)) r
             (not (contributory-fn (:bytes r)))
             {:status :error :reason :non-contributory-dh}
             :else r)))
   :pk-of (fn [sk] {:status :ok :bytes (pk-fn sk)})})

(def x25519-hkdf-sha256
  (montgomery-kem :x25519 0x0020 32 32 kdf/hkdf-sha256
                  x25519/x25519 x25519/public-key x25519/contributory?))

(def x448-hkdf-sha512
  (montgomery-kem :x448 0x0021 64 56 kdf/hkdf-sha512
                  x448/x448 x448/public-key x448/contributory?))

;; ── the NIST KEMs ────────────────────────────────────────────────────────────

(defn- nist-kem
  [nm kem-id nsecret nsk npk the-kdf curve-key bitmask]
  (let [c (get curve/curves curve-key)]
    {:name nm :kem-id kem-id :suite-id (suite-id-for kem-id)
     :nsecret nsecret :nsk nsk :npk npk :nenc npk
     :kdf the-kdf :curve c :bitmask bitmask
     :dh (fn [sk pk] (ecdh/ecdh c (bn/of-bytes sk) pk))
     :pk-of (fn [sk] (ecdh/public-key c (bn/of-bytes sk)))}))

(def p256-hkdf-sha256 (nist-kem :p256 0x0010 32 32 65 kdf/hkdf-sha256 :p256 0xFF))
(def p384-hkdf-sha384 (nist-kem :p384 0x0011 48 48 97 kdf/hkdf-sha384 :p384 0xFF))
(def p521-hkdf-sha512 (nist-kem :p521 0x0012 64 66 133 kdf/hkdf-sha512 :p521 0x01))

(def kems
  "The five, by identifier. All five run."
  {0x0010 p256-hkdf-sha256 0x0011 p384-hkdf-sha384 0x0012 p521-hkdf-sha512
   0x0020 x25519-hkdf-sha256 0x0021 x448-hkdf-sha512})

;; ── DeriveKeyPair ────────────────────────────────────────────────────────────

(defn candidate-acceptable?
  "RFC 9180 §7.1.3's loop condition, as a predicate: a candidate scalar is
  taken when it is neither zero nor at-or-above the group order.

  It is a named function rather than an inline `if` because **the rejection
  path is unreachable by any test that supplies an ikm.** For P-256 a masked
  candidate lands outside the range with probability about 2^-32; for P-521
  the bitmask leaves 521 bits and the order is within 2^-260 of that. Neither
  can be searched for, and forcing the condition to `false` — accepting every
  first candidate — leaves the entire RFC suite green, which is what a branch
  nothing reaches looks like.

  So it is reached here, from a test, at the boundary."
  [sk order]
  (and (not (bn/zero? sk)) (bn/lt? sk order)))

(defn derive-key-pair
  "RFC 9180 §7.1.3. Deterministic in `ikm`, which is what makes a test vector
  possible at all.

  Returns `{:status :ok :private … :public …}`, both as byte vectors."
  [kem ikm]
  (let [k (:kdf kem)
        sid (:suite-id kem)
        dkp-prk (kdf/labeled-extract k sid [] "dkp_prk" ikm)]
    (if (:montgomery? kem)
      (let [sk (kdf/labeled-expand k sid dkp-prk "sk" [] (:nsk kem))
            pk (:pk-of kem)]
        (let [p (pk sk)]
          (if (= :ok (:status p))
            {:status :ok :private sk :public (:bytes p)}
            p)))
      ;; Rejection sampling. The counter is bounded at 255 by the RFC, and
      ;; running out is an error rather than a weaker key: the alternative is
      ;; to accept a candidate at or above the order, which is a different
      ;; scalar than the one the peer will derive.
      (let [order (:n (:curve kem))]
        (loop [counter 0]
          (if (> counter 255)
            {:status :error :reason :derive-key-pair-exhausted}
            (let [cand (kdf/labeled-expand k sid dkp-prk "candidate" [counter] (:nsk kem))
                  cand (assoc (vec cand) 0 (bit-and (nth cand 0) (:bitmask kem)))
                  sk (bn/of-bytes cand)]
              (if-not (candidate-acceptable? sk order)
                (recur (inc counter))
                (let [p ((:pk-of kem) cand)]
                  (if (= :ok (:status p))
                    {:status :ok :private cand :public (:bytes p)}
                    p))))))))))

(defn derive-key-pair!
  [kem ikm]
  (let [r (derive-key-pair kem ikm)]
    (if (= :ok (:status r)) r
        (throw (ex-info (str "dhkem: " (name (:reason r))) r)))))

;; ── encapsulation ────────────────────────────────────────────────────────────

(defn- extract-and-expand
  [kem dh kem-context]
  (let [k (:kdf kem) sid (:suite-id kem)
        eae-prk (kdf/labeled-extract k sid [] "eae_prk" dh)]
    (kdf/labeled-expand k sid eae-prk "shared_secret" kem-context (:nsecret kem))))

(defn- dh! [kem sk pk on-error]
  (let [r ((:dh kem) sk pk)]
    (if (= :ok (:status r))
      r
      (if (= :non-contributory-dh (:reason r))
        r
        {:status :error :reason on-error :detail (:reason r)}))))

(defn encap
  "Encapsulate to `pk-r`. `eph` is the ephemeral key pair; it is a parameter
  rather than generated here because randomness is a capability and this is a
  leaf — and because a caller who cannot supply it cannot test.

  **A fresh ephemeral per encapsulation is mandatory.** Reusing one makes two
  encapsulations to the same recipient share a key and a base nonce, and every
  AEAD RFC 9180 names is a stream cipher underneath."
  [kem pk-r eph]
  (let [d (dh! kem (:private eph) pk-r :bad-recipient-key)]
    (if (not= :ok (:status d))
      d
      (let [enc (:public eph)]
        {:status :ok
         :enc enc
         :shared-secret (extract-and-expand kem (:bytes d) (vec (concat enc pk-r)))}))))

(defn decap
  "Decapsulate `enc` with the recipient's key pair."
  [kem enc kp-r]
  (if (not= (:nenc kem) (count enc))
    {:status :error :reason :bad-encapsulation-length :length (count enc)}
    (let [d (dh! kem (:private kp-r) enc :bad-encapsulation)]
      (if (not= :ok (:status d))
        d
        {:status :ok
         :shared-secret (extract-and-expand
                         kem (:bytes d) (vec (concat enc (:public kp-r))))}))))

;; ── the authenticated KEM, RFC 9180 §4.1 ─────────────────────────────────────
;;
;; The same construction with the sender's static key mixed in. Two things
;; change and both matter:
;;
;;   the DH input      DH(skE, pkR) || DH(skS, pkR)   -- two products, not one
;;   the KEM context   enc || pkRm || pkSm            -- three keys, not two
;;
;; The second is what makes the authentication mean anything. Without pkSm in
;; the context, a recipient holding a valid encapsulation from someone else
;; could not tell the two apart; the shared secret is bound to *which* sender,
;; not merely to the fact that some static key was used.

(defn auth-encap
  "RFC 9180 §4.1 AuthEncap. `kp-s` is the sender's static key pair.

  The recipient learns that whoever sent this holds `skS`. It does not learn
  it in a way it can show to anyone else — both parties can compute the same
  secret, so a transcript proves nothing to a third party. That deniability is
  what distinguishes this from a signature, and it is a feature of the mode
  rather than a shortfall of it."
  [kem pk-r eph kp-s]
  (let [de (dh! kem (:private eph) pk-r :bad-recipient-key)]
    (if (not= :ok (:status de))
      de
      (let [ds (dh! kem (:private kp-s) pk-r :bad-recipient-key)]
        (if (not= :ok (:status ds))
          ds
          (let [enc (:public eph)]
            {:status :ok
             :enc enc
             :shared-secret (extract-and-expand
                             kem
                             (vec (concat (:bytes de) (:bytes ds)))
                             (vec (concat enc pk-r (:public kp-s))))}))))))

(defn auth-decap
  "RFC 9180 §4.1 AuthDecap. `pk-s` is the sender's static public key.

  A wrong `pk-s` does not fail here — it derives a different shared secret,
  and the failure surfaces as the AEAD rejecting the first message. That is
  the specified behaviour: the KEM has nothing to compare against, so
  authentication is enforced by decryption rather than by a check with its own
  error."
  [kem enc kp-r pk-s]
  (cond
    (not= (:nenc kem) (count enc))
    {:status :error :reason :bad-encapsulation-length :length (count enc)}

    (not= (:npk kem) (count pk-s))
    {:status :error :reason :bad-sender-key-length :length (count pk-s)}

    :else
    (let [de (dh! kem (:private kp-r) enc :bad-encapsulation)]
      (if (not= :ok (:status de))
        de
        (let [ds (dh! kem (:private kp-r) pk-s :bad-sender-key)]
          (if (not= :ok (:status ds))
            ds
            {:status :ok
             :shared-secret (extract-and-expand
                             kem
                             (vec (concat (:bytes de) (:bytes ds)))
                             (vec (concat enc (:public kp-r) pk-s)))}))))))
