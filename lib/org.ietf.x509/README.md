# kotoba-lang/org-ietf-x509

**[RFC 5280](https://www.rfc-editor.org/rfc/rfc5280.html) certificate parsing —
the subset a signature verifier needs**, portable `.cljc`, on top of
`kotoba-lang/org-ietf-asn1`.

```clojure
(require '[x509.core :as x509])

(def cert (x509/parse der))
(:text (:x509/subject cert))              ;=> "CN=Kotoba Test TSA,O=…,C=JP"
(x509/has-extended-key-usage? cert :kp-time-stamping)  ;=> true
(x509/valid-at? cert "2026-08-01T00:00:00Z")           ;=> true
(x509/usable? cert)                       ;=> {:usable? true :reasons []}
(x509/verify-signature cert issuer verify-fn)          ;=> {:verified true}
```

## What it will not do

Not a path validation engine, and that is a decision rather than a TODO. Full
RFC 5280 §6 brings name constraints, policy mapping, CRL and OCSP — and every
one of those turns on **fetching something**. A library that fetched would hand
every caller an SSRF surface driven by attacker-supplied certificate contents,
which is exactly why `org-w3-vc-data-integrity` requires an injected
`:resolve-key`.

So: `verify-signature` takes the issuer's parsed certificate and an injected
`verify-fn`; `valid-at?` takes the time. **No clock, no network, no keys.**

Taking the time rather than reading a clock also buys the question an evidence
record actually needs — not "is it valid now" but "was it valid when it signed".

## Three refusals that are not optional

1. **outer `signatureAlgorithm` = `tbsCertificate.signature`** (§4.1.1.2). The
   same fact written twice, and only the inner one is signed. A verifier that
   reports one and checks the other can be shown a certificate that says
   `sha256WithRSA` and is verified as something else.
2. **an unrecognised CRITICAL extension makes the certificate unusable** (§4.2).
   `critical` means "reject this if you do not understand it". Parsing on and
   ignoring it inverts the one bit whose purpose is to be un-ignorable.
3. **absent `BasicConstraints` is not permission.** `ca?` is false for both
   "says false" and "says nothing".

A fourth, smaller: `has-extended-key-usage?` answers **false** for an absent
EKU. RFC 5280 reads absent as unrestricted, but the callers here are asking "is
this a timestamping certificate", and answering yes for one that never said so
is how a TLS key gets honoured as a TSA.

## Serial numbers are hex

Up to 20 octets — above what a double represents exactly, and an identifier
rather than a quantity. `openssl x509 -serial` prints hex for the same reason.
`asn1.core/integer-value` refuses anything that large rather than returning an
approximation, because CMS matches certificates **by serial**.

## Names

`:rdns` keeps order (it is part of a distinguished name); `:attributes` is for
reading a `CN` in a log. **Comparison is `:der` byte equality** — textual DN
comparison needs RFC 4518 preparation, and `IssuerAndSerialNumber` means the
bytes anyway.

## Test

```bash
kbb -M:test    # against two certificates OpenSSL produced, not ones this built
kbb -M:lint
```

Apache-2.0.
