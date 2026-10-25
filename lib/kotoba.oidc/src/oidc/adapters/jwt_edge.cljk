(ns oidc.adapters.jwt-edge
  "RS256 ID-token verification on WebCrypto — the adapter that lets OIDC run
  in a Cloudflare Worker, where `oidc.adapters.jwt-rsa` cannot go because it
  imports `java.security`.

  ## The seam is deliberately NOT `jwks/IJwksVerifier`

  That protocol's `verify-jwt!` returns the result. WebCrypto's
  `crypto.subtle.verify` returns a Promise, and there is no way to make an
  async primitive satisfy a synchronous protocol without blocking, which a
  Worker isolate cannot do. So this namespace exposes `verify-rs256!`
  returning a Promise instead of reifying the protocol and lying about it.

  What IS shared is `oidc.adapters.jwt-claims` — the decisions. Both adapters
  answer \"which JWK\" and \"are these claims acceptable\" with the same code,
  so the two deployments cannot drift into accepting different tokens. The
  result vocabulary matches jwt-rsa's exactly (`:unsupported-algorithm`,
  `:missing-jwk`, `:invalid-signature`, `:invalid-jwt`, plus a claim keyword
  under `:error`) so a caller that already handles one handles the other.

  ## What this verifies, and what it does not

  It verifies: the header names RS256, a published JWK with the token's `kid`
  signed the exact `header.claims` bytes presented, and `iss` / `aud` / `exp` /
  `nbf` are acceptable.

  It does NOT verify `nonce` — that is a replay question, and replay is
  answered by a store that can consume a value once
  (`oidc.ports/INonceStore`), not by inspecting a token in isolation. A
  verifier that checked `nonce` by string equality would look like replay
  protection and provide none.

  It also does not fetch JWKS. Key rotation, caching and the failure mode when
  an IdP is unreachable are the caller's policy, and a verifier that fetched
  on demand would turn every malformed token into an outbound request."
  (:require [oidc.adapters.jwt-claims :as jc]))

(defn- b64url->bytes
  "base64url (no padding) → Uint8Array. `atob` wants standard base64, so the
  alphabet is translated and the padding restored — a length ≡ 1 (mod 4) is
  not a valid base64url encoding at all and yields nil rather than a silently
  truncated buffer."
  [s]
  (let [n (mod (count s) 4)]
    (when (not= 1 n)
      (let [pad (case n 2 "==" 3 "=" "")
            std (-> s (.replace (js/RegExp. "-" "g") "+")
                    (.replace (js/RegExp. "_" "g") "/"))
            bin (js/atob (str std pad))
            out (js/Uint8Array. (.-length bin))]
        (dotimes [i (.-length bin)]
          (aset out i (.charCodeAt bin i)))
        out))))

(defn- b64url->string [s]
  (when-let [bytes (b64url->bytes s)]
    (.decode (js/TextDecoder. "utf-8") bytes)))

(defn- decode-json-part
  "One JWT segment → a keywordized map, or nil. Anything that is not a JSON
  object (a bare string, an array, garbage) is nil: a header or claim set that
  is not a map cannot be reasoned about by the claim rules."
  [seg]
  (try
    (let [s (b64url->string seg)
          v (when s (js->clj (js/JSON.parse s) :keywordize-keys true))]
      (when (map? v) v))
    (catch :default _ nil)))

(defn- import-rsa-key
  "JWK → CryptoKey for RSASSA-PKCS1-v1_5 / SHA-256.

  The JWK is handed to WebCrypto with `alg` and `key_ops` forced rather than
  passed through: an IdP that publishes `\"alg\":\"RS512\"` or omits `key_ops`
  must not be able to steer which algorithm this verifier then uses — the
  algorithm was already decided by `jc/header-error`."
  [jwk]
  (js/crypto.subtle.importKey
   "jwk"
   #js {:kty "RSA" :n (:n jwk) :e (:e jwk) :alg "RS256" :ext true}
   #js {:name "RSASSA-PKCS1-v1_5" :hash "SHA-256"}
   false
   #js ["verify"]))

(defn verify-rs256!
  "→ Promise of the claims map (with `:jwt-ref`) or `{:error <keyword> …}`.

  `opts`: `:jwks` (required — a JWKS map or a vector of JWKs), `:issuer`,
  `:audience`, `:now` (epoch seconds; defaults to the wall clock).

  Claim failures are reported the way jwt-rsa reports them — the claims map
  with `:error` set — so a caller can log which claim failed without a second
  shape to handle."
  [token {:keys [jwks issuer audience now] :as _opts}]
  (let [parts (jc/split-jwt token)
        [header-seg claims-seg sig-seg] parts
        header (when parts (decode-json-part header-seg))
        claims (when parts (decode-json-part claims-seg))
        sig (when parts (b64url->bytes sig-seg))
        alg-err (when header (jc/header-error header))]
    (cond
      (or (nil? parts) (nil? header) (nil? claims) (nil? sig))
      (js/Promise.resolve {:error :invalid-jwt})

      alg-err
      (js/Promise.resolve {:error alg-err :alg (:alg header)})

      :else
      (if-let [jwk (jc/matching-jwk jwks header)]
         (-> (import-rsa-key jwk)
             (.then (fn [key]
                      (js/crypto.subtle.verify
                       #js {:name "RSASSA-PKCS1-v1_5"}
                       key
                       sig
                       (.encode (js/TextEncoder.) (str header-seg "." claims-seg)))))
             (.then (fn [ok?]
                      (if-not ok?
                        {:error :invalid-signature}
                        ;; Claims are only inspected once the signature holds.
                        ;; Reporting "expired" for a token nobody signed would
                        ;; tell an attacker which of their forgeries parsed.
                        (let [now* (or now (quot (.now js/Date) 1000))]
                          (if-let [err (jc/claim-error claims {:issuer issuer
                                                               :audience audience
                                                               :now now*})]
                            (assoc claims :error err)
                            (assoc claims :jwt-ref token))))))
             (.catch (fn [e]
                       ;; An unusable JWK (bad modulus, wrong kty) lands here.
                       ;; It is a key problem, not a signature problem, and
                       ;; saying so keeps the two apart in the audit trail.
                       {:error :invalid-jwk :message (str (.-message e))})))
        (js/Promise.resolve {:error :missing-jwk :kid (:kid header)})))))
