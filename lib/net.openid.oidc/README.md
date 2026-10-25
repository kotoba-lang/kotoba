# kotoba-lang/org-openid-oidc

[![CI](https://github.com/kotoba-lang/org-openid-oidc/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-openid-oidc/actions/workflows/ci.yml)

Handle the **OpenID Connect Core** ID Token / discovery / UserInfo surface **as EDN/Clojure data** in
portable Clojure — every namespace is `.cljc`, with **zero third-party runtime deps**, so it runs
identically on the JVM, ClojureScript, and SCI/bb hosts.

This repo never fabricates trust: it does not verify JWT signatures and does not talk to the network.
`decode-jwt-segments` only splits a compact JWT into header/claims maps via an *injected* `json-read`
capability; `validate-id-token-claims` only checks the claims per [OIDC Core §3.1.3.7](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation)
(`iss`/`aud`/`exp`/`iat`/`nonce`) once a host has already verified the signature (RS256/ES256/etc. —
that's the host's job, not this library's).

Sibling of [`kotoba-lang/org-ietf-oauth2`](https://github.com/kotoba-lang/org-ietf-oauth2) — OIDC layers
on OAuth2's authorization-code flow — but this repo has no hard code dependency on it.

See [`kotoba-lang/oidc`](https://github.com/kotoba-lang/oidc) for the
result-shape substrate layer that composes this with other auth factors
(host-port pattern, no network/crypto here either, but a different
abstraction level).

## Usage

```clojure
(require '[oidc.core :as oidc])

;; 1. split + decode a compact JWT (signature verification is the host's job)
(oidc/decode-jwt-segments jwt-string json-read)
;; => {:header {...} :claims {...} :signing-input "hdr.payload" :signature [...]}

;; 2. validate the claims once the signature has been verified
(oidc/validate-id-token-claims claims {:issuer "https://issuer.example"
                                        :audience "client-id-1"
                                        :nonce "n-abc123"})
;; => {:valid? true :errors []}

;; 3. normalize a discovery document
(oidc/parse-discovery-document decoded-well-known-json)

;; 4. build a UserInfo request
(oidc/userinfo-request {:userinfo-endpoint (:userinfo-endpoint discovery) :access-token token})
```

## Test

```bash
kbb -M:test
```
