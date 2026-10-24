# kotoba-lang/org-ietf-sd-jwt-vc

**[SD-JWT VC](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-sd-jwt-vc) —
SD-JWT-based Verifiable Digital Credentials, portable `.cljc`.**

Composition, not new cryptography: `org-ietf-sd-jwt` provides the salted-hash
mechanism, `org-ietf-jws` the signature envelope, and this adds the rules that make
the pair a credential — a type, claims that can never be optional, and a holder
proof bound to one presentation.

## Seven claims that cannot be selectively disclosed

`iss`, `nbf`, `exp`, `cnf`, `vct`, `vct#integrity`, `status` MUST NOT appear in
Disclosures. Each is load-bearing for the *Verifier's* decision: a credential whose
expiry, issuer, type or revocation pointer could be withheld is one the **Holder**
gets to choose the meaning of. `issue` refuses to conceal them rather than trusting
a caller to remember.

## `sd_hash` covers the presentation, trailing tilde included

RFC 9901 §4.3.1 hashes the US-ASCII bytes of `<JWT>~<D.1>~…~<D.N>~` — and *not* the
KB-JWT. Two consequences:

- **Omitting the trailing `~` produces a digest that fails against every other
  implementation.** `sd-hash` refuses a prefix without it rather than hashing anyway.
- **It is what binds the proof to *this* disclosure set.** A Holder who drops a
  Disclosure and reuses the KB-JWT changes the hashed bytes — tested, and the
  reason the mechanism exists.

## The holder key comes from `cnf`, never from the KB-JWT

Key Binding requires `cnf` in the credential. Verifying the KB-JWT against a key it
carries itself would let the Holder nominate themselves, so a missing `cnf` is
refused when key binding is required, and the caller supplies `:verify-holder`
resolved from `cnf`.

`typ` is `dc+sd-jwt` for the Issuer-signed JWT and `kb+jwt` for the KB-JWT. The
older `vc+sd-jwt` is accepted on verification during the transition the draft
allows, and never produced. Explicit typing matters (RFC 8725): without it, a token
minted for another purpose under the same key could be presented as a credential.

## Test

```bash
kbb -M:dev:test              # JVM — real Ed25519 for both issuer and holder
kbb -M:lint
npm install && npm run smoke     # the :cljs branch
```

Both suites pin the same `sd_hash` literal. §4.3.1 hashes exact bytes, so a host
disagreement would surface as `:sd-jwt-vc/bad-sd-hash` — which reads as tampering
and is not.

## License

MIT. See `LICENSE`.
