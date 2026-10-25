# kotoba-lang/org-ietf-sd-jwt

**[RFC 9901](https://www.rfc-editor.org/rfc/rfc9901.html) — Selective Disclosure
for JWTs, portable `.cljc`.** The salted-hash mechanism itself: an Issuer replaces
a claim's value with a digest and hands the cleartext over separately, a Holder
chooses which of those Disclosures to forward, and a Verifier puts back only what
it was given.

This is the enterprise privacy primitive — *prove you are an auditor at Acme
without revealing your name* — and it needs no signature to be meaningful, which
is why it is separable from the JWS that carries it.

```clojure
(require '[sd-jwt.core :as sd])

(def issued
  (sd/conceal {"iss" "https://acme.example" "role" "auditor" "name" "Alice"}
              [["name"]]
              {:json-encode json/write-str :salt-fn my-csprng}))
;; :payload      → sign this   {"iss" … "role" "auditor" "_sd" ["…"] "_sd_alg" "sha-256"}
;; :disclosures  → give these to the holder

;; The holder shows the credential but withholds the name:
(sd/disclose (:payload issued) [] codec)
;=> {"iss" "https://acme.example" "role" "auditor"}
```

## The one thing to get right

§4.2.3: **the digest is computed over the US-ASCII bytes of the base64url-encoded
Disclosure**, not over the JSON inside it. Two consequences, both load-bearing:

1. Hashing the decoded JSON instead — the intuitive reading — produces digests no
   other implementation can reproduce.
2. Because the Verifier re-hashes *the string it received*, the Issuer's exact
   serialization never has to be reproduced. **No canonicalization is required
   anywhere in SD-JWT**, unlike Data Integrity. A whitespace difference is simply
   part of the bytes that were hashed.

## Reject versus ignore is asymmetric, deliberately

§7.1 requires **rejecting** the whole SD-JWT for a duplicate digest, or for a
Disclosure that was presented but never referenced. But an embedded digest with no
matching Disclosure MUST be **ignored** — that is the normal case, since it is
exactly what a claim the Holder chose to withhold looks like.

Collapsing those two into one behaviour breaks either selective disclosure or the
integrity check, depending which way you collapse it. Both are tested.

## What this does not do

**No JWS.** It does not sign, verify or parse a compact JWS, and does not check
`iss`/`exp`/`cnf` or a Key Binding JWT. `conceal`/`disclose` operate on the payload
as data, which is what makes them testable without a key. A JWS layer belongs above
this and can use `kotoba-lang/org-ietf-ed25519` or the P-256 primitives in
`kotoba-lang/org-w3-vc-data-integrity`.

**No ambient authority.** The salt source and the JSON codecs are injected: this
library has no business holding a CSPRNG, has no JSON dependency and does not want
one, and a test needs a deterministic salt.

## Fail-closed inputs

| `:sd-jwt/error` | Cause |
|---|---|
| `:sd-jwt/duplicate-digest` | §7.1 — a second copy would let one Disclosure fill two slots |
| `:sd-jwt/unused-disclosure` | §7.1 — presented but never referenced |
| `:sd-jwt/unsupported-sd-alg` | anything but `sha-256`; treating it as sha-256 makes every digest mismatch for the wrong reason |
| `:sd-jwt/weak-salt` | under 128 bits, which makes a digest brute-forceable over the value |
| `:sd-jwt/claim-absent` | concealing a claim that is not there |
| `:sd-jwt/missing-trailing-separator` | §4 — without the trailing `~` the last Disclosure reads as a Key Binding JWT |

## Test

```bash
kbb -M:dev:test                     # JVM
kbb -M:lint
npm install && npm run smoke            # the :cljs branch
```

Both suites pin the **same** digest literal for the same Disclosure string. §4.2.3
hashes those exact bytes, so if the hosts ever disagree, an Issuer on one emits
digests a Verifier on the other cannot reproduce — and the failure is **silent**,
because an unmatched digest reads as a withheld claim rather than an error.

## License

MIT. See `LICENSE`.
