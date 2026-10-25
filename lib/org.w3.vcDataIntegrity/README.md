# kotoba-lang/org-w3-vc-data-integrity

**[W3C Data Integrity](https://www.w3.org/TR/vc-data-integrity/) proofs for
Verifiable Credentials and Presentations, portable `.cljc`.** Two cryptosuites:
`eddsa-jcs-2022` ([vc-di-eddsa](https://www.w3.org/TR/vc-di-eddsa/), Ed25519) and
`ecdsa-jcs-2019` ([vc-di-ecdsa](https://www.w3.org/TR/vc-di-ecdsa/), P-256).

## Which cryptosuite

`eddsa-jcs-2022` is the default. Pass `{:suite ecdsa/suite}` for P-256, which is
what every WebAuthn credential uses and therefore what every `did:key:zDna…`
subject is. Without it such a credential is not merely unsupported but
**rejected**, which to its holder is indistinguishable from being forged.

Two things `ecdsa-jcs-2019` gets right that are easy to get wrong:

- **`proofValue` is IEEE P1363, not DER** — a bare `r ‖ s`, exactly 64 bytes for
  P-256 (§3.3.1, RFC 4754 §7). The JVM's ordinary `SHA256withECDSA` emits a
  variable-length DER SEQUENCE that nobody else would accept, so this uses
  `SHA256withECDSAinP1363Format` and produces the raw form directly rather than
  converting — a DER→P1363 conversion is one more place to be subtly wrong.
- **A P-256 `did:key` carries a compressed point.** Recovering `y` is a single
  `modPow` because P-256's `p ≡ 3 (mod 4)`; getting the sign convention backwards
  yields a key that parses and verifies nothing, so the tests assert `y` and not
  only `x`.

**ECDSA signatures here are not reproducible.** §3 only *SHOULD*s determinism and
the JVM provider is randomized, so unlike Ed25519 this suite cannot be pinned to a
fixed `proofValue` — an external vector can only be *verified*. That is asserted
rather than left as a surprise. The P-256 primitives are `:clj` only; `:cljs`
raises a clear error rather than doing something else.

`kotoba-lang/org-w3-vc` builds and shape-checks a credential but treats `proof`
as an opaque pass-through field. This is what actually puts a signature in it.
Together they are a VC implementation; separately neither is.

```clojure
(require '[data-integrity.core :as di])

(def secured
  (di/issue-credential
    {"@context" ["https://www.w3.org/ns/credentials/v2"]
     "type" ["VerifiableCredential"]
     "issuer" "did:key:z6Mk…"
     "credentialSubject" {"id" "did:example:1" "role" "auditor"}}
    {:seed seed-bytes
     :verification-method "did:key:z6Mk…#z6Mk…"
     :created "2026-07-30T00:00:00Z"}))

(di/verify-credential secured)
;=> {:verified true :verification-method "did:key:z6Mk…#z6Mk…"
;    :proof-purpose "assertionMethod" :document {…}}
```

Presentations bind to a verifier-issued challenge:

```clojure
(def vp (di/issue-presentation
          {"@context" ["https://www.w3.org/ns/credentials/v2"]
           "type" ["VerifiablePresentation"]
           "holder" holder-did
           "verifiableCredential" [secured]}
          {:seed holder-seed :verification-method holder-vm
           :created "2026-07-30T00:00:00Z"
           :challenge "nonce-from-the-verifier"
           :domain "https://verifier.example"}))

(di/verify-presentation vp {:challenge "nonce-from-the-verifier"
                            :domain "https://verifier.example"})
```

## Verified against the specification's own test vector

The suite pins W3C vc-di-eddsa Appendix B.3 — not a round-trip, an equality.
Ed25519 (RFC 8032) is deterministic, so the exact `proofValue` is reproducible:

| Checked | Value |
|---|---|
| `transformedDocumentHash` | `59b7cb6251b8991a…abc92f19` |
| `proofConfigHash` | `66ab154f5c2890a1…e539a1db` |
| `proofValue` | `z2HnFSSPPBzR36zdDgK8PbEHeXbR56YF24jwMpt3R1eHXQzJDMWS93FCzpvJpwTWd3GAVFuUfjoJdcnTMuVor51aX` |

This matters because every *other* test in the file is self-consistency:
issue-then-verify passes just as happily if the hash order, the canonicalization
and the multibase prefix are all wrong in the same direction on both sides. The
fixed vector comes from outside, so it cannot be wrong in the same direction as
the code. It also externally validates `kotoba-lang/org-ietf-jcs`, since
`transformedDocumentHash` is a SHA-256 over its output.

## The one thing that is easy to get backwards

§3.3.4: `hashData` = **SHA-256(canonicalProofConfig) ‖ SHA-256(transformedDocument)**.

The proof-configuration digest comes *first*. Reversed, you get a valid-looking
64-byte value whose signatures verify against nothing, and the failure is
indistinguishable from a wrong key. `hash-data` asserts the order against the
fixed vector, and asserts the reversed order is *not* what it produces.

## Two deliberate departures from the letter of the spec

Both toward fail-closed, both documented at their call site.

1. **`verify` requires `:expected-proof-purpose`.** The spec makes the check
   conditional ("if expectedProofPurpose was given"), so a spec-literal
   verifier's *default* behaviour is to accept a credential signed for
   `authentication` where `assertionMethod` was meant — which lets a captured
   login proof stand in for an issuer's assertion. Pass `:any` to opt back into
   the unchecked behaviour.
2. **`verify-presentation` requires `:challenge`.** A presentation proof with
   nothing binding it to a request is replayable by anyone who observes it once.

A third, smaller one: §3.3.3 step 1 says an error must be raised if the type is
wrong **and** the cryptosuite is wrong, which taken literally lets a
`DataIntegrityProof` with some other cryptosuite through. §3.3.5 step 2 states the
same guard with `or`. We use `or`.

## What it will not do for you

- **No clock.** `:created` is required and never defaulted, the same discipline
  `kotoba-lang/ao` follows by taking `now-ms` from its caller. The timestamp
  inside a signature is always one the caller chose and can reproduce.
- **No network.** `did:key` resolves locally and completely. `did:web` does not:
  resolving it means fetching `https://…/did.json`, and a
  signature-verification library that reaches the network on its own hands every
  caller an unasked-for outbound dependency and an SSRF surface driven by
  attacker-supplied document content. Pass `:resolve-key` for `did:web`; the
  error tells you the URL.
- **No key custody.** Pass `:sign` instead of `:seed` and an HSM or KMS produces
  the signature; key material never enters this library.
- **No proof sets or `previousProof` chains.** Re-signing an already-secured
  document is refused rather than silently signing different bytes than the
  caller believes.
- **No credential status.** See `kotoba-lang/org-w3-vc-bitstring-status-list`.
- **No JSON-LD processing.** `eddsa-jcs-2022` canonicalizes JSON, not RDF, so
  `@context` values are compared but never dereferenced. The `-rdfc-` suites,
  which do need RDF Dataset Canonicalization, are not implemented.

## `@context` and the prefix rule

§3.3.2 step 4 requires the secured document's `@context` to *start with* every
value in the proof's `@context`, in the same order. Appending a context therefore
keeps the issuer's signature valid, while prepending or removing one is rejected
— otherwise a holder could steer how a verifier interprets a document the issuer
signed. All three cases are tested.

## An invalid proof is `false`, not an exception

Only a **malformed** input throws. A forged signature, a wrong purpose, a
mismatched challenge or domain, and a bad `@context` prefix all return
`{:verified false :reason <keyword>}`. Callers must branch on `:verified` and must
never treat "did not throw" as success.

## Dependencies

| Repo | For |
|---|---|
| `kotoba-lang/org-ietf-jcs` | RFC 8785 canonicalization (the transformation step) |
| `kotoba-lang/org-ietf-ed25519` | RFC 8032 sign/verify, `did:key` → public key |
| `kotoba-lang/org-w3-did` | DID parsing, `did:web` URL derivation |
| `kotoba-lang/io-multiformats` | SHA-256, multibase base58-btc |

`data-integrity.bytes` exists because those libraries disagree about what
"bytes" means and the disagreement is silent — `base58btc-decode` alone returns
a byte-array on `:clj` and a **vector of ints** on `:cljs`. One normal form
(vector of ints 0..255), converted at the crypto boundary only.

## Test

```bash
kbb -M:test          # JVM, release deps (git SHAs)
kbb -M:dev:test      # JVM, sibling west checkouts
kbb -M:lint
npm install && npm run smoke   # the :cljs branch
```

The `:cljs` branch needs its own run, and CI runs both. Every dependency here has
a reader-conditional split and two of them have already diverged silently:
`jcs.core` refused a valid `1e20` on `:cljs` because `Number.isInteger` is not the
analogue of `integer?`, and `multiformats.core/base64url-decode` returns a
byte-array on `:clj` but a **vector of ints** on `:cljs`. A signature is over
exact bytes, so a host that assembles them differently produces a credential the
other host cannot verify — with nothing to say so.

`test/nbb_smoke.cljk` therefore pins the *same* W3C Appendix B.3 vector the JVM
suite pins, including reproducing the exact `proofValue`. Measured 2026-07-30:
both hosts produce it byte for byte.

`@noble/hashes` is a runtime dependency of the `:cljs` path only —
`multiformats.core` reaches for it for SHA-256. It is declared in `package.json`
because without it a fresh clone cannot run the smoke test; it previously
appeared to work only because a sibling repo happened to have `node_modules`.

## License

MIT. See `LICENSE`.
