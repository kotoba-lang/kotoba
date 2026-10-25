# custody

**Threshold custody for sealed secrets: `m` of `n` custodians must agree
before anything opens — and a check that the `m` actually means something.**

The pure half is `.cljc` with no runtime dependencies and runs identically on
the JVM and under nbb (22 tests / 83 assertions, the same files on both).
`custody.seal` is the ClojureScript half that supplies the randomness, the
SHA-256 and the X25519 wrap (6 more tests, real Web Crypto — 28 / 103 total).

```clojure
(require '[custody.shamir :as shamir] '[custody.model :as custody])

;; 3-of-5, one share per custodian, custodians in different domains
(def shares (shamir/split recovery-key 3 5 secure-random-bytes))

(def deal
  (custody/deal "deal:itonami/recovery/2026-07"
    {:secret-id     "envelope:drv:abc123#recovery"
     :threshold     3
     :total         5
     :secret-digest (sha256-b64 recovery-key)
     :custodians    [{:custodian/id "did:key:z6Mk…" :custodian/domain :tenant   :custodian/pub "…"}
                     {:custodian/id "did:key:z6Mk…" :custodian/domain :tenant   :custodian/pub "…"}
                     {:custodian/id "did:key:z6Mk…" :custodian/domain :operator :custodian/pub "…"}
                     {:custodian/id "did:key:z6Mk…" :custodian/domain :notary   :custodian/pub "…"}
                     {:custodian/id "did:key:z6Mk…" :custodian/domain :counsel  :custodian/pub "…"}]}))

(custody/independence deal)
;=> {:independence/min-domains-to-open 2
;    :independence/captured-by         nil
;    :independence/can-deny            #{:tenant}
;    :independence/sound?              true}

(custody/open deal releases sha256-b64)
;=> {:custody/opened? true :custody/secret […]}
```

## Why `independence` is the point

Splitting a secret 3-of-5 is arithmetic, and the arithmetic is easy. The part
that is easy to get wrong — and impossible for the algebra to notice — is
**who holds the shares**. Three of five shares sitting in one operator's
control is a 1-of-1 wearing a costume. `custody.model/independence` is the
check that says so:

- `:independence/captured-by` — the domain that can open the secret alone.
  Non-nil means the threshold is decorative.
- `:independence/min-domains-to-open` — the fewest distinct parties that can
  reach the threshold together. `1` is the same failure stated as a number.
- `:independence/can-deny` — domains that can make recovery *impossible* by
  refusing. Reported, but deliberately **not** part of `sound?`: a tenant that
  can block its own recovery is usually the intent; an operator that can is a
  hostage situation, and this library will not guess which one you meant.

`:independence/sound?` is the invariant worth gating a deployment on — and
`custody.seal/split-and-wrap!` **gates on it by default**, rejecting rather
than handing back a 3-of-5 that is really a 1-of-1. Forcing it is possible
(`:require-sound? false`, for a tenant who deliberately wants nobody but
itself to be able to recover) but a caller that passes it is stating that on
the record.

## Actually opening something

`custody.seal` (ClojureScript, Promise-returning, same reason as
`envelope.seal`: Web Crypto has no synchronous API) is where the injected
randomness and digest get supplied exactly once:

```clojure
(-> (seal/split-and-wrap! {:deal-id    "deal:itonami/recovery/2026-07"
                           :secret-id  "envelope:drv:abc123#recovery"
                           :secret     recovery-key
                           :threshold  3
                           :custodians [{:custodian/id "did:key:…" :custodian/domain :tenant   :custodian/pub "…"} …]})
    (.then (fn [{:keys [deal]}] (store! deal))))          ; no plaintext share in it

(-> (js/Promise.all #js [(seal/release! deal c1 priv1 {:at now :reason "…"})
                         (seal/release! deal c3 priv3 {:at now :reason "…"})
                         (seal/release! deal c5 priv5 {:at now :reason "…"})])
    (.then #(seal/open! deal (vec %))))
;=> {:custody/opened? true :custody/secret […]}
```

The wrap is `envelope.seal/wrap-bytes` — the same X25519 + HKDF-SHA256 +
AES-256-GCM construction that wraps an envelope's content key, given
`model/share-aad` instead. That binding is what makes a wrap
non-transplantable, and it is load-bearing rather than decorative: a
custodian using its own private key against another custodian's wrap, or
against its own wrap relabelled to a different coordinate, or under a deal
claiming a different epoch, **does not decrypt** — AES-GCM refuses, with no
check anywhere in this library's own code. `the-operator-alone-cannot-open-it`
and `a-custodian-cannot-unwrap-another-custodians-share` run that against
real wraps rather than arguing it.

## What it does not do

- **No crypto primitives in the pure half.** `shamir/split` takes a
  `rand-bytes-fn`; `model/open` takes a `digest-fn`. A portable namespace
  cannot honestly claim a secure RNG on every runtime this workspace targets,
  and one that quietly fell back to `rand-int` would be worse than one with
  no opinion. `custody.seal` supplies both on the runtime that has them, and
  delegates the wrap to
  [`kotoba-lang/envelope`](https://github.com/kotoba-lang/envelope) rather
  than writing a second X25519.
- **It does not hide the secret's length.** Every share is exactly as long as
  the secret. Pad first if that matters.
- **Shamir alone cannot tell you the quorum was wrong.** Combine the wrong
  shares and you get a different secret, not an error — there is no redundancy
  in the algebra to notice with. That is what `:deal/secret-digest` is for,
  and why `shamir/combine` is deliberately the *unverified* primitive while
  `model/open` is the one you should call. The test
  `a-wrong-quorum-returns-a-plausible-secret-instead-of-an-error` pins the
  behaviour so it is documented by a passing assertion rather than discovered
  during a recovery.
- **Rotation is not an epoch bump.** `model/rotate` returns a *shell* with the
  custodians and digest cleared, because re-splitting and re-wrapping is the
  only thing that actually retires old shares. Bumping the epoch stops old
  shares from being accepted; it does not make a custodian who already
  unwrapped one forget it — the same honesty `envelope.model/revoke` applies
  to a deleted wrap.

## Structural refusals

`model/quorum-error` reports disagreement before insufficiency, so a caller
collecting shares sees the real problem as soon as it appears:

| reason | what it caught |
|---|---|
| `:foreign-deal` / `:foreign-secret` | a share for something else |
| `:mixed-epoch` | a share from a retired generation being replayed |
| `:unknown-share-x` | a coordinate belonging to no custodian |
| `:custodian-share-mismatch` | a custodian presenting someone else's coordinate |
| `:share-x-disagreement` | the release and the share inside it disagree |
| `:duplicate-share` | the same custodian counted twice |
| `:below-threshold` | not enough, checked last |

## Lineage

Replaces the `kotoba-custody` Rust crate cited by ADR-2607061900, removed with
the rest of the Rust tree (ADR-2607072000). The `GrantedShare` shape that ADR
described — epoch, deal binding, per-requester re-wrap — is what `share-aad`
and `quorum-error` reconstruct in `.cljc`. Consumed by the cloud-itonami
sealed plane (ADR-2607285000).

```bash
kbb -M:test        # JVM: the pure half, 22 tests / 83 assertions
npm install && npm test # nbb: adds custody.seal, 28 / 103 with real Web Crypto
```

AGPL-3.0-or-later.
