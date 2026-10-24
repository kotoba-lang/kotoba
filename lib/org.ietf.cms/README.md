# kotoba-lang/org-ietf-cms

**[RFC 5652](https://www.rfc-editor.org/rfc/rfc5652.html) `SignedData`** —
parse, verify, build. Portable `.cljc` on `org-ietf-asn1` + `org-ietf-x509`.

```clojure
(require '[cms.core :as cms] '[cms.jvm :as jvm])

(def sd (cms/parse-signed-data der))
(cms/verify sd {:digest-fn jvm/digest :verify-fn jvm/verify})
;=> {:verified true :signers [{:verified true :signed-attrs? true :signing-time "…"}]}

;; detached — the content is REQUIRED, not optional
(cms/verify sd {:content bytes :digest-fn jvm/digest :verify-fn jvm/verify})
```

## The bug this is mostly written to prevent

When `signedAttrs` is present, **the signature does not cover the content.** It
covers the DER of the attributes. The content is reached only through the
`messageDigest` attribute, and that link exists only if somebody checks it.

The mistake: verify the signature over `signedAttrs`, see that it is
cryptographically valid, report the content as signed — never comparing
`messageDigest` to the content in hand. Every byte of content verifies. **Any
content verifies.**

A verifier with that bug passes every positive test ever written for it, because
the signature really is valid. So the suite swaps the content out from under a
genuine signature and asserts both that verification fails *and* that the
signature over the attributes is still valid — the second half is what makes the
first half mean something.

Four refusals guard the same seam:

| refused | what it stops |
|---|---|
| `messageDigest` missing | a signature that mentions no content at all |
| `contentType` ≠ `eContentType` | a signature over an RFC 3161 token replayed as one over data |
| a single-valued attribute with many values | the honest digest supplied next to any other |
| detached content the caller did not pass | "verified over nothing" reading as verified |

Zero signers is `:verified false`, not vacuously true.

## signedAttrs are re-tagged before hashing

They travel as `[0] IMPLICIT` and are hashed **as a `SET`** (§5.4) — one byte
different. `asn1.core/retag` drops the parsed `:asn1/der` so the wire bytes
cannot be hashed by accident, which would produce a signature no conforming
verifier accepts and which a self-consistent implementation would never notice.

## Injected crypto

`:digest-fn` and `:verify-fn` are arguments. No keys and no algorithm fallback
live in the core, for the reason `x509.core` and `data-integrity.core` both
give. `cms.jvm` (`:clj` only, so a `.cljs` consumer gets a missing namespace
rather than one that pretends) supplies ready-made ones and **refuses an
algorithm it cannot name** — a registry with a default is how a signature made
with one algorithm gets checked with another.

`build-signed-data` takes a `sign-fn`; the private key never enters this library.

## Test

```bash
kbb -M:test    # against SignedData OpenSSL produced, attached and detached
kbb -M:lint
```

Apache-2.0.
