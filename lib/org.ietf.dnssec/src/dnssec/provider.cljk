(ns dnssec.provider
  "The reference crypto injection for `dnssec.sign` — Ed25519 signing (RFC 8080)
  and SHA-2 digests, wired to `kotoba-lang/ed25519` and the host's own hash.

  `dnssec.sign` takes `sign-fn` and `digest-fn` as arguments and imports no
  crypto, so that a zone-signing key can live in an HSM, in `kagi`, or in a
  JVM `KeyStore` and never pass through the serialization code. That boundary
  is the point, and this namespace does not weaken it: it is **one** possible
  injection, kept separate so a caller with a real key store can ignore it
  entirely and pass their own two functions.

  Requiring `dnssec.canonical` or `dnssec.sign` does not load this namespace,
  so the pure half stays usable without ever touching a key.

  ## Byte representations

  `dnssec.sign` speaks vectors of 0-255 ints; `ed25519.core` speaks host byte
  arrays. The conversion happens here, once, rather than at every call site —
  and it masks on the way back, because `vec` of a JVM `byte[]` yields *signed*
  bytes and a signature whose octets came back as -128 instead of 0x80 will not
  verify against the same signature that went out.

  ## What is deliberately not here

  A **Worker** path. WebCrypto's `digest` and `sign` are asynchronous, and
  `dnssec.sign` is synchronous by construction because the signed blob has to
  be assembled deterministically in one pass. Zone signing is a job, not a
  request handler, so JVM or Node is the right place for it — and pretending
  otherwise would mean an API that returns promises for a computation that has
  no reason to be async."
  (:require [kotoba.lang.text] [dnssec.sign :as sign]
            [ed25519.core :as ed])
  #?(:clj (:import (java.security MessageDigest))))

;; ── byte conversion ───────────────────────────────────────────────────────

(defn ->host-bytes
  "Vector of 0-255 ints → the byte array `ed25519.core` and the host digest
  APIs expect."
  [v]
  #?(:clj (byte-array (map unchecked-byte v))
     :cljs (js/Uint8Array.from (clj->js (vec v)))))

(defn ->octets
  "Host byte array → vector of 0-255 ints. The mask is load-bearing: on the JVM
  `vec` of a `byte[]` gives signed values, so 0x80 comes back as -128 and any
  comparison against the octets that went onto the wire fails."
  [b]
  (mapv #(bit-and % 0xFF) (vec (seq #?(:clj b :cljs (array-seq b))))))

;; ── digests ───────────────────────────────────────────────────────────────

(def ^:private digest-algorithm
  "DS digest type → the host's name for it (RFC 4034 §5.1.4, RFC 6605). SHA-1
  (type 1) is absent for the same reason `dnssec.sign/digests` omits it: RFC
  8624 deprecates it, and a name that cannot be typed cannot be chosen."
  {:sha256 "SHA-256" :sha384 "SHA-384" 2 "SHA-256" 4 "SHA-384"})

(defn digest-fn
  "`(fn [digest-type octets] -> octets)` for `dnssec.sign/ds`.

  An unknown digest type raises rather than falling back to SHA-256: a DS
  record whose digest field says one algorithm and whose bytes are another is
  a delegation that silently fails to validate everywhere."
  [digest-type octets]
  (let [algo (or (digest-algorithm digest-type)
                 (throw (ex-info "unsupported DS digest type" {:digest-type digest-type})))]
    (->octets
     #?(:clj (.digest (MessageDigest/getInstance ^String algo) (->host-bytes octets))
        :cljs (let [c (js/require "crypto")]
                (-> (.createHash c (kotoba.lang.text/lower (kotoba.lang.text/replace algo "-" "")))
                    (.update (js/Buffer.from (->host-bytes octets)))
                    (.digest)))))))

;; ── signing ───────────────────────────────────────────────────────────────

(defn sha1-fn
  "SHA-1, for NSEC3 (RFC 5155 §5). It is the only hash the protocol defines,
  and NSEC3 needs **preimage** resistance rather than collision resistance, so
  SHA-1's known weakness is not the one that would matter here. It is also not
  a choice: IANA has registered no alternative.

  Kept apart from `digest-fn` so nothing can reach for SHA-1 as a DS digest,
  where collision resistance IS what is being relied on and RFC 8624 deprecates
  it."
  [octets]
  #?(:clj (.digest (MessageDigest/getInstance "SHA-1") (->host-bytes octets))
     :cljs (let [c (js/require "crypto")]
             (-> (.createHash c "sha1")
                 (.update (js/Buffer.from (->host-bytes octets)))
                 (.digest)))))

(defn sign-fn
  "`(fn [algorithm seed octets] -> signature-octets)` for `dnssec.sign/rrsig`.

  `seed` is the raw 32-byte Ed25519 private seed. Only `:ed25519` (algorithm
  15, RFC 8080) is implemented; the ECDSA and RSA algorithms in
  `dnssec.sign/algorithms` are legitimate choices this provider simply does not
  cover, and it says so rather than signing with the wrong curve."
  [algorithm seed octets]
  (when-not (#{:ed25519 15} algorithm)
    (throw (ex-info "this provider signs Ed25519 (algorithm 15) only; supply your own sign-fn for the others"
                    {:algorithm algorithm})))
  (->octets (ed/sign (->host-bytes seed) (->host-bytes octets))))

(defn verify-fn
  "`(fn [algorithm pubkey octets signature] -> boolean)`.

  `dnssec.sign` is a signer and does not verify anything, so this exists for
  the caller that wants to check its own output before publishing — which is
  worth doing, because a zone that fails validation looks to the world like a
  zone that is not signed at all."
  [algorithm pubkey octets signature]
  (when-not (#{:ed25519 15} algorithm)
    (throw (ex-info "this provider verifies Ed25519 (algorithm 15) only" {:algorithm algorithm})))
  (try
    (boolean (ed/verify (->host-bytes pubkey) (->host-bytes octets) (->host-bytes signature)))
    (catch #?(:clj Exception :cljs :default) _ false)))

;; ── convenience ───────────────────────────────────────────────────────────

(defn public-key
  "The raw 32-byte Ed25519 public key for a seed, as octets — what goes into
  the DNSKEY record."
  [seed]
  (->octets (ed/pubkey-from-seed (->host-bytes seed))))

(defn sign-rrset
  "Sign one RRset with this provider. Thin wrapper over `dnssec.sign/rrsig`
  that fills in `sign-fn`, so the common case does not have to repeat it."
  [records params]
  (sign/rrsig records (assoc params :sign-fn sign-fn)))

(defn delegation-signer
  "The DS record for a DNSKEY, with this provider's digest. The one artifact
  that has to leave the registry and be published in the *parent* zone —
  without it, a correctly signed zone is, to every validator, unsigned."
  [dnskey-record params]
  (sign/ds dnskey-record (assoc params :digest-fn digest-fn)))
