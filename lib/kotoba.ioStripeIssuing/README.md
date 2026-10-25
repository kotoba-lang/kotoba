# io-stripe-issuing

[![CI](https://github.com/kotoba-lang/io-stripe-issuing/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/io-stripe-issuing/actions/workflows/ci.yml)

**A live Stripe Issuing provider for
[`kotoba.card.actuation`](https://github.com/kotoba-lang/card).** This is the layer
that actually issues a card — deliberately the only thing in the family that can.

Same arrangement as `kotoba-lang/drive` (contract) + `io-storj` (provider): neither
library depends on the other, and a host depends on both.

## Why this is not a `kotoba.card.ports` implementation

`kotoba.card.ports` is **propose-only** and says so: a host that actuates inside
one of those methods has moved a licensed act behind an interface that reads as a
query. So the live provider implements the *other* protocol,
`kotoba.card.actuation`, and the names differ by a bang at every call site:
`ports/issue-card` **drafts**, `actuation/issue-card!` **does**.

## What is and is not verified

This matters more than usual, so it is stated before anything else.

**Verified against the live Stripe API spec on 2026-07-30 (`2026-06-24.preview`):**

- `GET /v1/issuing/cards` and `/v1/issuing/cardholders` exist
- card `status` is one of `active` / `inactive` / `canceled`
- card `type` is one of `virtual` / `physical`

**NOT verified through tooling — written from knowledge of the API:**

- the POST bodies for `/v1/issuing/cardholders` and `/v1/issuing/cards`
- the `replacement_for` / `cancellation_reason` fields

The MCP surface available during this build exposes only *read* operations for
Issuing, so the write shapes could not be checked the way the statuses were.
**Treat every write path as unexercised until it has run against Stripe test
mode.** `mode` defaults to `:test`, and `describe` reports
`:write-paths-unexercised true` so a caller cannot mistake this for proven.

That run is now written and waiting for a key:

```bash
STRIPE_TEST_KEY=sk_test_... kbb -M:exercise
```

It creates a cardholder, issues a virtual card, then activates, blocks and closes it,
printing each request and answer — the point is to learn whether the SHAPES are right,
and a green run that printed nothing would leave this section just as unproven.

**It cannot touch live.** `mode` is no longer a note: a key whose own prefix disagrees
with the mode is refused before a request is built, by the same check the provider uses.
`sk_live_` here is refused, and so is a test key on a `:live` provider — the first would
issue real cards while every log said test, the second would do nothing real while a
deployment believed it was issuing.

## The state mapping, published rather than absorbed

`kotoba.card.actuation/state-mapping-complete?` requires a provider to account for
**every** lifecycle state, mapping to `nil` the ones it cannot express. Folding is
forbidden, because that is how `:issued` and `:active` become the same thing and a
card that was never activated starts working.

| lifecycle | Stripe `card.status` | |
|---|---|---|
| `:intake` | *(none)* | no Stripe object exists yet |
| `:issued` | `inactive` | created, not usable |
| `:active` | `active` | |
| `:blocked` | `inactive` | **collides with `:issued`** |
| `:closed` | `canceled` | terminal at both ends |

> **The collision is the point.** `:issued` and `:blocked` both map to `inactive`,
> so Stripe alone cannot tell them apart — and the difference matters: one is a card
> that has never worked, the other is a card that was working and was stopped. A
> provider that reconstructed the lifecycle state from Stripe would answer `:issued`
> for a blocked card, and a caller acting on that would "activate" a card a human
> deliberately blocked.
>
> So **this provider does not reconstruct state from Stripe.** The issuer side's
> recorded state is the authority; `card-state` returns the *set* of candidates plus
> `:card/unambiguous` (nil for `inactive`), and Stripe is corroboration, not truth.

**A reissue is refused, not approximated.** Stripe replaces a card by creating a new
one with `replacement_for` and cancelling the original — two calls, not a status
change. Approximating it with a cancel would leave a caller believing a replacement
exists when none does, so `set-card-state!` refuses `:reissue` with a hint to run
it as two separately approved actuations.

## Guards

Every write runs `actuation/precheck` **before any outbound call**:

- an **approval naming both** who (`:by`) and what (`:reference`) — a reference with
  no approver cannot be audited, and an approver with no reference cannot be tied to
  what they saw
- a **caller-supplied idempotency key**, not generated here: only the caller knows
  whether this is a retry, and a retried `issue-card!` must not produce a second
  live card. It goes out as Stripe's `Idempotency-Key` header.

A provider that reached the network and *then* discovered the approval was unnamed
has already acted — so the tests assert **no call was recorded**, not merely that a
refusal came back.

Refusals are **data**, never exceptions: a Stripe 402, a connection failure and an
unsupported card type all come back as `{:card/ok? false :card/refusal {…}}` so a
governed actor can record what the provider said.

## No credential lives here

The secret key is read from an environment variable **named by the caller**
(`STRIPE_SECRET_KEY` by default) at call time, and is never stored on the provider
record — so a provider value cannot leak one by being printed. `describe` is
asserted to contain no secret-shaped string. With no key configured, the transport
refuses rather than sending an unauthenticated request.

## Run

```bash
kbb -M:test    # 40 tests / 141 assertions — no network, no key needed
kbb -M:lint    # clj-kondo, 0 errors 0 warnings
```

Every test drives a **recorded transport** that answers from a map and records each
call, which is what makes the "refuses before calling" guarantee testable at all.

```clojure
(require '[io.stripe.issuing.core :as stripe]
         '[kotoba.card.actuation :as actuation])

(def p (stripe/provider))                     ; :test mode, STRIPE_SECRET_KEY

(actuation/issue-card! p "ich_123" {:card-type "virtual"}
                       {:by "operator@example" :reference "commit-p1-abc"}
                       "idem-1")
;=> {:card/ok? true :card/reference "ic_…" :card/state :issued …}
```

## Maturity

| | |
|---|---|
| Role | provider (`:provider` in the stack-tier vocabulary) |
| Contract implemented | `kotoba.card.actuation` (post-approval) |
| Tests | 40 tests / 141 assertions, all green — recorded transport only, plus the state mapping incl. the `inactive` collision |
| Lint | clj-kondo 0 errors, 0 warnings |
| Read paths | shapes verified against the live spec |
| **Write paths** | **unexercised — not yet run against Stripe test mode** |
| Live mode | `:mode :live` must be set deliberately; default is `:test` |
| Portability | JVM only (`java.net.http`), unlike the `.cljc` contract it implements |

## Design authority

**ADR-2607300300** (`com-junkawasaki/root`, `90-docs/adr/`). Created because the
integration's card path had a governed actor and a propose-only port layer and
nothing that could actually issue — and because the owner named Stripe Issuing as
the intended issuer.

## License

Apache-2.0. See [LICENSE](LICENSE).
