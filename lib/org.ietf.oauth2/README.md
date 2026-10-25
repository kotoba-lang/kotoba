# kotoba-lang/org-ietf-oauth2

[![CI](https://github.com/kotoba-lang/org-ietf-oauth2/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ietf-oauth2/actions/workflows/ci.yml)

Handle **OAuth 2.0 (RFC 6749) and PKCE (RFC 7636) as EDN/Clojure data** in
portable Clojure — every namespace is `.cljc`, with **zero third-party
runtime deps**, so it never makes a network call or a cryptographic call
itself. This is the raw external-spec substrate — building the
authorization URL, parsing the redirect callback, shaping a token request
body, normalizing a token response, deriving a PKCE code verifier/challenge
— the same "raw spec, not kotoba's own vocabulary" placement as
`kotoba-lang/org-materialx` / `kotoba-lang/org-w3-webgpu` (ADR-2607051400
precedent). HTTP transport and the SHA-256/randomness PKCE needs are
**host-injected capabilities**, the same seam `kotoba-lang/godaddy-dns`
uses for its HTTP/JSON calls.

See [`kotoba-lang/oauth`](https://github.com/kotoba-lang/oauth) for the
result-shape substrate layer that composes this with other auth factors
(host-port pattern, no network/crypto here either, but a different
abstraction level).

## Usage

```clojure
(require '[oauth2.core :as oauth2]
         '[oauth2.pkce :as pkce])

;; 1. PKCE (optional, recommended) — sha256-fn/random-bytes-fn come from your host
(def verifier (pkce/generate-code-verifier my-random-bytes-fn))
(def challenge (pkce/code-challenge verifier my-sha256-fn))

;; 2. Send the user to the authorization URL
(oauth2/authorization-url
  {:authorize-endpoint "https://as.example.com/authorize"
   :client-id "abc123"
   :redirect-uri "https://app.example.com/cb"
   :scope "openid profile"
   :state "xyz"
   :code-challenge (:code-challenge challenge)
   :code-challenge-method (:code-challenge-method challenge)})

;; 3. Parse the redirect callback
(oauth2/parse-authorization-response {:code "SplxlOBeZQQYbYS6WxSbIA" :state "xyz"})
;; => {:code "SplxlOBeZQQYbYS6WxSbIA" :state "xyz"}

;; 4. Shape the token request, POST it yourself, parse the response
(oauth2/token-request-body {:grant-type "authorization_code" :code "..." ...})
(oauth2/parse-token-response decoded-json-body)
```

## Test

```bash
kbb -M:test
```
