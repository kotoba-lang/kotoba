# kotoba-lang/org-oasis-saml

[![CI](https://github.com/kotoba-lang/org-oasis-saml/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-oasis-saml/actions/workflows/ci.yml)

SAML 2.0 (the OASIS identity-federation standard) as data — "hiccup for identity
federation". An `AuthnRequest` / `Assertion` / `Response` is a plain EDN/Hiccup vector you
build, fork, and diff; `render` compiles it to an XML string on top of
[`kotoba-lang/xml`](https://github.com/kotoba-lang/xml)'s dependency-free Hiccup emitter.
Every namespace is `.cljc`, zero third-party runtime deps.

Reverse-domain named (`org-oasis-saml`, not bare `saml`) for the same reason as
`org-materialx`/`org-khronos-gltf`/`org-openusd`/`org-w3-webgpu`: SAML is a spec owned by an
external standards body (OASIS) with its own domain, and a bare `saml` slug risks colliding
with an unrelated kotoba-lang vocabulary name later.

See [`kotoba-lang/saml`](https://github.com/kotoba-lang/saml) for the
result-shape substrate layer that composes this with other auth factors
(host-port pattern, no network/crypto here either, but a different
abstraction level).

## What's in here — and what isn't

This is the raw SAML 2.0 protocol/assertion *substrate*: building the right elements with the
right attributes. It does **not** sign, verify, or encrypt anything (XML-DSig / XML-Enc are
host-owned — real IdPs and SPs require a signed assertion, so a host must inject real signing
before sending, and real signature verification before trusting an inbound one) and it does
**not** parse inbound XML (there is no SAML XML parser here, matching `xml.core` being
emit-only). `parse-attributes` exists purely to document the EDN shape a host hands back
after it has parsed and verified a real `<saml:Assertion>`.

## Usage

```clojure
(require '[saml.core :as saml])

(def req
  (saml/authn-request {:id "_req1"
                        :issue-instant "2026-07-05T00:00:00Z"
                        :destination "https://idp.example/sso"
                        :issuer "https://sp.example"
                        :assertion-consumer-service-url "https://sp.example/acs"}))

(saml/render req)
;; => "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<samlp:AuthnRequest ...>\n  <saml:Issuer>...</saml:Issuer>\n</samlp:AuthnRequest>"

(def resp
  (saml/response {:id "_resp1" :issue-instant "2026-07-05T00:00:00Z"
                   :destination "https://sp.example/acs" :issuer "https://idp.example"
                   :assertion (saml/assertion {:id "_a1" :issue-instant "2026-07-05T00:00:00Z"
                                                :issuer "https://idp.example"
                                                :subject-name-id "alice@example.com"
                                                :conditions-not-before "2026-07-05T00:00:00Z"
                                                :conditions-not-on-or-after "2026-07-05T00:10:00Z"
                                                :audience "https://sp.example"
                                                :attributes {"email" ["alice@example.com"]}})}))
```

## Test

`deps.edn` resolves `io.github.kotoba-lang/xml` via `{:local/root "../xml"}` — clone
[`kotoba-lang/xml`](https://github.com/kotoba-lang/xml) as a sibling directory first (this is
the same layout `org-materialx` uses, matching the `orgs/kotoba-lang/*` sibling checkout
convention in `com-junkawasaki/root`):

```sh
git clone https://github.com/kotoba-lang/xml ../xml   # if not already a sibling checkout
kbb -M:test
```
