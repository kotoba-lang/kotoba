(ns teams.jwt-verify
  "Async RS256 JWT signature verification for the Bot Framework's inbound
  `Authorization: Bearer <JWT>` webhook header — Cloudflare Workers/
  browser only (Web Crypto's `SubtleCrypto.verify` is Promise-based, same
  reason every other async-signature namespace in this workspace is
  `.cljs`-only). Structural parsing + claims (`iss`/`aud`/`exp`) live in
  the portable `teams.jwt` — this ns is ONLY the cryptographic signature
  check plus the JWKS fetch/lookup it needs.

  **Unverified against Microsoft's real infrastructure** (ns-wide caveat,
  also in this library's ADR): the JWKS fetch URL and RS256 verification
  steps are implemented per Microsoft's published Bot Framework
  authentication docs, but this code has never actually been run against
  a live Bot Framework token issuer (no deployed bot exists yet to
  generate one). Every other webhook signature in this workspace (Meta,
  LINE, Viber) is symmetric HMAC and was exercised against
  self-generated known-answer test vectors; RS256 asymmetric verification
  against a THIRD PARTY's live public keys cannot be fully exercised the
  same way without a real Bot Framework registration."
  (:require [teams.jwt :as jwt]))

(def bot-framework-jwks-url
  "https://login.botframework.com/v1/.well-known/keys")

(defn fetch-jwks!
  "GET the Bot Framework JWKS (`{:keys [...]}`, each entry a JWK). `fetch-fn`
  is injected (`(fetch-fn url) -> js/Promise<parsed-jwks>`) so callers can
  cache across requests (a Worker calling this per-webhook-request would
  otherwise re-fetch the same rarely-rotating key set every time) and so
  this stays testable without a real network call."
  [fetch-fn]
  (fetch-fn bot-framework-jwks-url))

(defn- find-jwk [jwks kid]
  (first (filter #(= kid (:kid %)) (:keys jwks))))

(defn- jwk->crypto-key [jwk]
  (.importKey js/crypto.subtle "jwk" (clj->js jwk)
              #js {:name "RSASSA-PKCS1-v1_5" :hash "SHA-256"}
              false #js ["verify"]))

(defn- base64url->bytes [s]
  (let [s     (-> s (.replace (js/RegExp. "-" "g") "+") (.replace (js/RegExp. "_" "g") "/"))
        pad   (mod (- 4 (mod (.-length s) 4)) 4)
        s     (str s (apply str (repeat pad "=")))
        binary (js/atob s)
        bytes  (js/Uint8Array. (.-length binary))]
    (dotimes [i (.-length binary)]
      (aset bytes i (.charCodeAt binary i)))
    bytes))

(defn verify-signature!
  "`token`: the raw JWT string (just the token, no \"Bearer \" prefix --
  caller strips that). `jwks`: an already-fetched JWKS map (see
  `fetch-jwks!`). Returns `js/Promise<boolean>` -- false (not a rejected
  promise) for a malformed token or an unknown `kid`, so a caller can
  `.then` uniformly without a separate `.catch` branch for \"this JWT is
  garbage\" vs \"the crypto check ran and failed\"."
  [token jwks]
  (if-let [{:keys [header-b64 payload-b64 signature-b64]} (jwt/split-jwt token)]
    (let [header (jwt/decode-segment #(js->clj (js/JSON.parse %) :keywordize-keys true) header-b64)
          jwk    (find-jwk jwks (:kid header))]
      (if-not jwk
        (js/Promise.resolve false)
        (-> (jwk->crypto-key jwk)
            (.then (fn [key]
                     (.verify js/crypto.subtle "RSASSA-PKCS1-v1_5" key
                              (base64url->bytes signature-b64)
                              (.encode (js/TextEncoder.) (str header-b64 "." payload-b64)))))
            (.catch (fn [_] false)))))
    (js/Promise.resolve false)))
