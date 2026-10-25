(ns oidc.adapters.jwt-claims
  "The parts of ID-token verification that are decisions rather than crypto:
  which JWK signed this, and are the claims acceptable.

  ## Why this namespace exists

  `oidc.adapters.jwt-rsa` verifies on the JVM (`java.security.Signature`) and
  `oidc.adapters.jwt-edge` verifies in a Cloudflare Worker (WebCrypto). Those
  two cannot share the signature step — one is synchronous and one returns a
  Promise — but they MUST share the answer to \"is this token acceptable\".

  A second copy of `claim-error` is not a duplication smell, it is a security
  bug waiting for its first divergence: the day one side gains a clock-skew
  allowance, or stops checking `nbf`, or starts accepting an array `aud` the
  other rejects, tokens become acceptable on one deployment and not the other
  — and the JVM side is where the tests live, so the edge is where the gap
  would go unnoticed.

  Everything here is pure and platform-free: maps in, keyword out."
  (:require [kotoba.lang.text :as str]))

(defn audience-match?
  "RFC 7519 allows `aud` to be a string or an array of strings. Both forms
  must be handled, and an array must match on membership rather than on
  equality with the whole array."
  [expected aud]
  (if (sequential? aud)
    (boolean (some #{expected} aud))
    (= expected aud)))

(defn claim-error
  "The first failing claim check, or nil.

  `opts`: `:issuer` `:audience` `:now` (epoch seconds). Issuer and audience
  are checked only when the caller supplied an expectation — a verifier that
  invented one would reject every token from a correctly configured IdP.
  Expiry is checked whenever the token carries it, because a token with no
  `exp` is a different (worse) problem than an expired one and is not this
  function's to conflate.

  Order matters for the message the caller reports, not for safety: every
  branch is a rejection."
  [claims {:keys [issuer audience now]}]
  (cond
    (and issuer (not= issuer (:iss claims))) :issuer
    (and audience (not (audience-match? audience (:aud claims)))) :audience
    (and (:exp claims) (<= (:exp claims) now)) :expired
    (and (:nbf claims) (> (:nbf claims) now)) :not-yet-valid
    :else nil))

(defn matching-jwk
  "The JWK from `jwks` that the token's header names, or nil.

  With a `kid`, only a key carrying that exact `kid` is a match. Without one,
  the first RSA key is used — which is why an IdP publishing several keys and
  omitting `kid` is a configuration this cannot disambiguate, and picking the
  first is the same behaviour the JVM adapter has always had.

  `kty` is filtered to RSA because both callers implement RS256 only; an EC
  key must not be handed to an RSA verifier just because it appeared first."
  [jwks header]
  (let [kid (:kid header)
        ks (or (:keys jwks) jwks)]
    (if kid
      (first (filter #(and (= "RSA" (:kty %)) (= kid (:kid %))) ks))
      (first (filter #(= "RSA" (:kty %)) ks)))))

(defn split-jwt
  "The three compact-serialization segments, or nil when the token is not a
  three-part JWT. Returns nil rather than throwing so both callers can map it
  onto their own `:invalid-jwt` result without a try/catch that would also
  swallow real errors."
  [token]
  (when (string? token)
    (let [parts (str/split token #"\.")]
      (when (= 3 (count parts)) parts))))

(def supported-alg
  "The only `alg` either adapter implements. Named rather than inlined so a
  future ES256 addition has one place to widen and one place to test."
  "RS256")

(defn header-error
  "Rejects a header this verifier must not act on. `alg: none` and any
  algorithm swap land here — the check is an allowlist against
  `supported-alg`, not a denylist of known-bad values, because the set of
  bad values is not enumerable."
  [header]
  (when-not (= supported-alg (:alg header)) :unsupported-algorithm))
