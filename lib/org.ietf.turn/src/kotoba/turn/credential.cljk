;; kotoba.turn.credential — TURN ephemeral-credential mint/verify, coturn
;; `use-auth-secret` scheme (the de-facto WebRTC standard; see RFC 7635 and
;; https://github.com/coturn/coturn/wiki/turnserver#turn-rest-api).
;;
;;   username   = "<expiry-unix-ts>:<user>"
;;   credential = base64( HMAC-SHA1( shared-secret, username ) )
;;
;; The HMAC-SHA1 primitive is reader-conditional: the JVM branch does the
;; RFC 2104 ipad/opad construction itself (identical shape to
;; `kotoba.bytes.sha1/hmac-sha1`) but delegates the actual digest to the
;; platform's `java.security.MessageDigest` SHA-1 (audited, JIT-compiled —
;; and, unlike `javax.crypto.Mac`/`SecretKeySpec`, it has no objection to an
;; empty key, which HMAC itself allows per RFC 2104 §2); the ClojureScript
;; branch uses the pure `kotoba.bytes.sha1` implementation (no native crypto
;; dependency, works in-browser or under Node without polyfills). Both
;; `kotoba.bytes` and `kotoba.bytes.sha1` come from `kotoba-lang/bytes`
;; (extracted from this repo; see README.md).
;; `credential_test.clj` cross-checks both paths against the same RFC 2202
;; vectors AND against each other directly (the pure impl is plain portable
;; code, so it's callable from JVM tests too) to pin them to identical bytes.
(ns kotoba.turn.credential
  (:require [kotoba.lang.text :as str]
            [kotoba.bytes :as b]
            [kotoba.bytes.sha1 :as sha1])
  #?(:clj (:import (java.security MessageDigest))))

#?(:clj
   (defn- jvm-sha1 [bs]
     (vec (map #(bit-and % 0xff)
               (.digest (MessageDigest/getInstance "SHA-1")
                        (byte-array (map unchecked-byte bs)))))))

(defn hmac-sha1-bytes
  "HMAC-SHA1 of byte-vector `msg` under byte-vector `key`. Returns a 20-byte
   vector (kotoba.bytes convention). This is the byte-level primitive —
   use this (not `hmac-sha1`) for STUN MESSAGE-INTEGRITY, whose key/message
   are arbitrary binary, not necessarily valid UTF-8 text."
  [key msg]
  #?(:clj
     (let [key' (if (> (count key) sha1/block-size) (jvm-sha1 key) (vec key))
           key-padded (b/pad-right key' (- sha1/block-size (count key')))
           opad (mapv (fn [k] (bit-xor k 0x5c)) key-padded)
           ipad (mapv (fn [k] (bit-xor k 0x36)) key-padded)]
       (jvm-sha1 (into opad (jvm-sha1 (into ipad msg)))))
     :cljs
     (sha1/hmac-sha1 key msg)))

(defn hmac-sha1
  "HMAC-SHA1 of UTF-8 string `msg` under UTF-8 string `secret`. Returns a
   20-byte vector (kotoba.bytes convention)."
  [^String secret ^String msg]
  (hmac-sha1-bytes (b/utf8-encode secret) (b/utf8-encode msg)))

(defn hmac-sha1-base64
  "HMAC-SHA1(secret, msg), base64-encoded (standard alphabet, padded)."
  [secret msg]
  (b/base64-encode (hmac-sha1 secret msg)))

(defn mint-credential
  "Mint a coturn-style ephemeral TURN credential for `user`, valid for
   `ttl-seconds` from `now` (unix seconds). Returns {:username :credential}.
   `shared-secret` must never reach a client — this runs server-side only."
  [shared-secret user ttl-seconds now]
  (let [expires-at (+ now ttl-seconds)
        username (str expires-at ":" user)]
    {:username username
     :credential (hmac-sha1-base64 shared-secret username)}))

(defn verify-credential
  "Verify a presented (username, credential) pair under `shared-secret` at
   time `now` (unix seconds). Returns true iff the username is well-formed,
   unexpired (expiry >= now), and the HMAC matches."
  [shared-secret username credential now]
  (boolean
    (when-let [colon (str/index-of username ":")]
      (let [expiry-str (subs username 0 colon)]
        (when (re-matches #"\d+" expiry-str)
          (let [expires-at #?(:clj (Long/parseLong expiry-str) :cljs (js/parseInt expiry-str 10))]
            (and (>= expires-at now)
                 (b/constant-time-eq credential (hmac-sha1-base64 shared-secret username)))))))))

;; --- room/player-scoped variant --------------------------------------------
;; The kotoba real-time signaling relay (kami-engine-sdk's WebRTC call layer,
;; `docs/ADR-kotoba-turn-relay.md`) scopes a credential's `user` segment to
;; `"<room>:<player>"` rather than a single opaque string, and its verify path
;; needs to report WHY a credential was rejected (malformed / bad-expiry /
;; expired / bad-signature) and hand back the parsed room/player on success —
;; a richer contract than the generic `mint-credential`/`verify-credential`
;; above. Built on the exact same `hmac-sha1-base64`/`constant-time-eq`
;; primitives; no new crypto, just a different username encoding + a result
;; shape mirroring the JS SDK's `TurnCredential`/`VerifyTurnResult`.

(defn mint-credential-scoped
  "Mint a room/player-scoped ephemeral TURN credential. Returns
   {:username :credential :expires-at}. `shared-secret` must never reach a
   client — this runs server-side only."
  [shared-secret room player ttl-seconds now]
  (let [expires-at (+ now ttl-seconds)
        username (str expires-at ":" room ":" player)]
    {:username username
     :credential (hmac-sha1-base64 shared-secret username)
     :expires-at expires-at}))

(defn verify-credential-scoped
  "Verify a room/player-scoped (username, credential) pair under
   `shared-secret` at time `now` (unix seconds). Returns
   {:ok true :room :player} on success, or {:ok false :reason} where reason
   is one of :malformed :bad-expiry :expired :bad-signature."
  [shared-secret username credential now]
  (let [parts (str/split username #":")]
    (if (not= 3 (count parts))
      {:ok false :reason :malformed}
      (let [[expiry-str room player-str] parts]
        (if-not (re-matches #"\d+" expiry-str)
          {:ok false :reason :bad-expiry}
          (let [expires-at #?(:clj (Long/parseLong expiry-str) :cljs (js/parseInt expiry-str 10))]
            (cond
              (< expires-at now)
              {:ok false :reason :expired}

              (not (b/constant-time-eq credential (hmac-sha1-base64 shared-secret username)))
              {:ok false :reason :bad-signature}

              :else
              {:ok true :room room :player #?(:clj (Long/parseLong player-str) :cljs (js/parseInt player-str 10))})))))))
