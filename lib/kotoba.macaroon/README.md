# macaroon

**A bearer token anyone holding it can narrow, and nobody can widen.**

> **Not the fleet's delegation centre — that is `kotoba-lang/org-biscuitsec`**
> (root ADR-2608180200). This is the narrow case: **the verifier already holds
> the root secret.** A macaroon chains an HMAC, so every place that verifies
> needs that secret, and kotobase verifies at the edge. Use it inside one
> trust domain; use a biscuit across principals.

```clojure
(require '[macaroon.core :as m] '[macaroon.authority :as ma])

(def t (m/mint {:location "kotobase.net" :identifier "tenant/acme"
                :root-key root-key :hmac-fn hmac}))

;; Attenuation needs NO key — this is the whole construction.
(def narrowed
  (-> t
      (m/attenuate {:caveat/kind :scope :caveat/scopes ["kotoba://graph/acme/prices"]} hmac)
      (m/attenuate {:caveat/kind :before :caveat/instant "2026-09-01T00:00:00Z"} hmac)
      (m/attenuate {:caveat/kind :holder :caveat/did "did:key:zBob"} hmac)))

(ma/authorize narrowed {:base base :root-key root-key :hmac-fn hmac
                        :requested "kotoba://graph/acme/prices"
                        :holder "did:key:zBob" :now "2026-08-18T00:00:00Z"})
;; => {:authority/allowed? true :macaroon/verified? true :authority/effective #:grant{…}}
```

    sig₀ = HMAC(root-key, identifier)
    sigₙ = HMAC(sigₙ₋₁, caveatₙ)

Appending a caveat means recomputing the chain, which anyone can do. Removing
one means inverting an HMAC, which nobody can. **Delegation with no round
trip, no registrar and no secret** — and the root key never leaves the
verifier.

## Two wires, one decider

This library does not decide anything. It answers *is this token intact and
are its caveats met*; what the resulting authority **covers** is
`kotoba-lang/authority`'s question, and `macaroon.authority` is the one-way
door between them.

That boundary is why a second token format costs nothing here.
`authority.scope` exists because `covers?` had been written once per URI
scheme, and one of those copies compared strings with `starts-with?` — so
`kotoba://graph/alice*` covered `kotoba://graph/alice-evil`. Adding
macaroons and biscuits adds **wires**. It must not add deciders.

```text
macaroon ─┐
biscuit  ─┼─→ inert grant ─→ authority.chain/authorize ─→ allowed?
CACAO    ─┤
UCAN     ─┘
```

`->grant` can only narrow, and not by discipline: scope caveats fold through
`authority.grant/meet`, which is a greatest lower bound. **A malicious caveat
is arithmetically incapable of granting anything.**

## Caveats are data, not strings

The paper makes a first-party caveat an opaque application string and the
verifier a list of predicates that try to match it. That is where macaroons
get fragile: a verifier that does not recognise a caveat must choose between
ignoring it — which **widens** the token — and refusing it.

Here a caveat is an EDN map with a `:caveat/kind`, and the choice is made
once, in the safe direction: **an unrecognised kind is not satisfiable.**

| kind | means | folds into |
|---|---|---|
| `:scope` | narrow to these resources | `scope/meet-sets` |
| `:before` | not after this instant | the tighter expiry |
| `:holder` | only this principal | the grant's holder |
| `:opaque` | anything else | an injected verifier, deny by default |

The first three are the ones a lattice can *fold* rather than merely check,
so three caveats narrowing scope produce one scope set and the result is
again a grant.

## Scored against the alternatives

Root ADR-2608180200, 0–5, weighted for this workspace. The row that decided it:

| | offline | **verify w/o secret** | attenuation | expressiveness | revocation | wire maturity | implemented here | total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| biscuit | 5 | **5** | 5 | 5 | 3 | 2 | 4 | 29 |
| UCAN | 5 | 5 | 5 | 3 | 4 | 4 | 4 | 30 |
| **macaroon** | 5 | **0** | 5 | 3 | 2 | 2 | 4 | **21** |
| CACAO | 5 | 5 | 2 | 2 | 3 | 4 | 5 | 26 |
| bearer token | 0 | 0 | 0 | 0 | 5 | 5 | 5 | 15 |

The zero is not a defect of the format; it is the format. Everything a
macaroon buys follows from the verifier holding the key that minted it.

## What it refuses

- **No default MAC.** `hmac-fn` is injected and there is no fallback: a token
  library with built-in crypto is a library that owns keys (`blind`'s
  reasoning, one layer up).
- **No wire compatibility claim.** `serialize` emits canonical EDN.
  libmacaroons v1/v2 binary is **not implemented**, and no external
  implementation has read anything this produces. Saying "macaroon format"
  before that is the claim `org-apache-parquet` learned to distrust from
  inside its own passing suite.
- **Third-party caveats are structural only** — `seal-fn` is injected and
  discharge-macaroon collection is not implemented.
- **It is a bearer token.** Possession is authority; that is the format, not
  a bug, and it is why `:holder` is a caveat. `org-biscuitsec` is the same
  idea with public-key attenuation, and the two are here for that contrast.

## Verification

`kbb -M:test` and `npm run test:nbb` — **18 tests, 39 assertions**, both
green, with a real HMAC-SHA-256 on both runtimes (not a stub: the
un-removability of a caveat is a property of a PRF).

Shown red on four real defects and green again with each reverted:

| broken | failures |
|---|---:|
| an unrecognised caveat kind is satisfied by default | 3 |
| a missing clock reads as "not expired" | 1 |
| scope caveats union instead of meet (widening) | 4 |
| the signature chain ignores caveat content | 9 |

The first of those was **found by the exercise**: the suite refused unknown
kinds at mint time and never checked the path they actually arrive by —
deserialization of a token minted by a newer version. That test now exists.
