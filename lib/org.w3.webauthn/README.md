# kotoba-lang/org-w3-webauthn

[![CI](https://github.com/kotoba-lang/org-w3-webauthn/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-w3-webauthn/actions/workflows/ci.yml)

W3C WebAuthn relying-party ceremony data as EDN, in portable Clojure — every
namespace is `.cljc`, with **zero third-party runtime deps**, so it runs
unchanged on the JVM, ClojureScript, and SCI.

This is the raw WebAuthn substrate: it builds the
`PublicKeyCredentialCreationOptions`/`PublicKeyCredentialRequestOptions`
maps the browser's `navigator.credentials.create()`/`.get()` needs, and
validates the parts of a response a relying party can check without
touching raw crypto (client-data type/challenge/origin, signature-counter
monotonicity). It does **not** call `navigator.credentials` itself, parse
CBOR attestation objects, or verify COSE signatures — those stay
host-injected, the same seam every langchain-clj host uses.

`bytes` throughout means a plain seq/vector of ints in `[0 255]`, not a
platform byte array, so the same code runs unchanged everywhere.

See [`kotoba-lang/webauthn`](https://github.com/kotoba-lang/webauthn) for the
result-shape substrate layer that composes this with other auth factors
(host-port pattern, no network/crypto here either, but a different
abstraction level).

## Usage

```clojure
(require '[webauthn.core :as webauthn])

(webauthn/creation-options
  {:rp-id "example.com" :rp-name "Example"
   :user-id [1 2 3 4] :user-name "alice" :user-display-name "Alice"
   :challenge (random-bytes 32)}) ; caller supplies real randomness

(webauthn/verify-client-data
  decoded-client-data-json ; host already ran JSON/decode
  {:expected-type "webauthn.get"
   :expected-challenge issued-challenge
   :expected-origin "https://example.com"})
;; => {:valid? true :errors []}
```

## Test

```bash
kbb -M:test
```
