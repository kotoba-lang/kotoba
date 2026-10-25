# crowdfunding

**Rewards-crowdfunding protocol primitives — pure `.cljc`, no network
I/O, no clock, no key custody.**

A [kotoba-lang](https://github.com/kotoba-lang) capability library for
running a campaign platform at the scale the category's incumbents
operate at: campaigns, reward tiers and add-ons, pledges as
authorizations, the collection window where some of those
authorizations fail, fees, creator payouts with holdbacks, launch
review, discovery, and post-funding fulfilment accountability.

Design record:
[ADR-2607268500](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607268500-crowdfunding-itonami-capability-and-actors.edn)
in the `com-junkawasaki/root` superproject. It replaces
`etzhayyim/com-etzhayyim-app-crowdfunding`, a TypeScript app whose
domain (campaign / pledge / settlement / 10% tithe) is absorbed here —
the tithe survives as a fee-schedule option, not as a hard-coded
constant.

## The one fact everything follows from

A pledge is an **authorization**, not a payment. The backer commits to
something that does not exist yet, at a price fixed today, and is
charged weeks later — if the campaign meets its goal. Almost every rule
in this library is a consequence:

| Consequence | Where |
|---|---|
| `:live -> :collecting` is not an edge; a campaign must pass through a decided outcome | `campaign/transitions` |
| Three totals — pledged, collected, at-risk — are reported and never collapsed | `funding/tally` |
| Cards fail between authorization and charge, so drop-off is a first-class number | `collection/finalize` |
| Fees are charged on collection, never on the pledged total | `fee/campaign-fees` |
| A backer may withdraw any time before the window closes | `pledge/cancellable?` |
| A creator is paid before shipping, so holdbacks are a schedule a backer can read | `payout/staged` |

## Invariants

1. **No custody.** Nothing here moves money, holds a key, or reaches the
   network. `payout/payout-plan` is a *computation*: an auditable
   statement of who should receive what. Executing it is the payout
   actor's separately human-approved step. Same boundary
   `kotoba-lang/pay` and `kotoba-lang/marketplace` keep.
2. **Conservation.** `platform + processing + tithe + net = charged`, and
   `tranches + holdback = net`, exactly, for every pledge and every plan.
   Both are computed onto the result (`:fee/conserved?`,
   `:payout/tranches-conserved?`) so a future edit that breaks the
   arithmetic fails a test rather than quietly losing money. Rounding
   dust flows to the creator, and to their *earliest* tranche.
3. **No adjudication.** There is no `approve`, no `resolve-dispute` that
   reads evidence and returns an outcome. `trust/review` returns
   findings; `trust/decision`, `payout/resolve-hold`,
   `campaign/reinstate` and `fulfillment/failure-disclosure` record what
   a **named human** decided and refuse (nil) without one.

## Namespaces

```clojure
crowdfunding.campaign     ; the funded thing + the state table that gates money
crowdfunding.reward       ; scarce, dated, shippable promises
crowdfunding.pledge       ; authorization vs payment, backer withdrawal rights
crowdfunding.funding      ; pledged / collected / at-risk, stretch goals, outcome
crowdfunding.collection   ; the charge window, retries, drop-off
crowdfunding.fee          ; the take rate, as checkable integers
crowdfunding.payout       ; creator payout, tranches, holdbacks, refunds
crowdfunding.passthrough  ; deposit + capped parts pass-through pricing
crowdfunding.trust        ; launch review — findings, never a verdict
crowdfunding.discovery    ; categories, cards, auditable ranking
crowdfunding.fulfillment  ; surveys, delivery, accountability
```

## Discovery has no thumb on it

On a crowdfunding platform, placement *is* funding, which makes ranking
the most consequential and most opaque power the operator has.
`discovery/rank` takes no boost parameter, has no creator-supplied
weight, returns `:ranking/exclusions` with a reason per excluded
campaign, and names its own `:ranking/key-fields` on the result. A
creator who was not shown can reproduce the result and see why. Ties
break on campaign id — a total order, so every visitor sees the same
feed. This is `marketplace.catalog/buy-box`'s discipline applied to a
feed.

A campaign with **no pledges yet is still listed**. Excluding it would
make the feed a rich-get-richer loop in which nothing new can start,
which is the difference between a market and a leaderboard.

## Fixed price is not the only pricing model

Fixed-price crowdfunding asks a creator to sell, today, a thing whose
inputs they buy in six months — an unhedged short on those inputs, fatal
when component prices move.
[ADR-2607268000](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607268000-murakumo-mk1-crowdfunding-4region-tax-asset.edn)
declined it for this workspace's own hardware campaign after DDR5 rose
448% in twelve months.

So `:campaign/pricing-model` also accepts `:deposit-plus-settlement`,
implemented by `crowdfunding.passthrough`: the backer commits a deposit
plus a fixed margin, the parts cost passes through at settlement, and the
whole thing is bounded by a cap the backer agreed to at pledge time.
There is no branch in `settle` that can bill a backer past their cap —
`reconsent` (a new agreement, a named backer, a strictly higher cap) is
the only way across. Over the cap, `:settlement/creator-absorbs-minor`
says what the creator eats, and `campaign-exposure` aggregates it,
because absorbing an overage on one order is a rounding error and
absorbing it on nine hundred is the end of the company.

The margin is a fixed amount in currency, not a percentage of parts cost
— a percentage margin means the creator *profits* from component
inflation, which is exactly the incentive that makes pass-through pricing
untrustworthy.

## What it composes

| Concern | Delegated to |
|---|---|
| Integer split allocation, dust convention | [`pay`](https://github.com/kotoba-lang/pay) |
| Escrow states, payout destinations, fee-schedule shape | [`marketplace`](https://github.com/kotoba-lang/marketplace) |
| Identity verification outcomes (passed in, never performed here) | [`ekyc`](https://github.com/kotoba-lang/ekyc) |
| Sanctions / AML status (passed in; `:not-run` is a finding, not a pass) | [`aml`](https://github.com/kotoba-lang/aml) |
| Index / tokenize / score over `discovery/search-doc` | [`search`](https://github.com/kotoba-lang/search) |

## Governed by actors, not by this library

This library decides nothing that moves money. The four
`cloud-itonami` actors do that, each with an independent governor, a
langgraph-clj StateGraph and an append-only audit ledger:

| Actor | Owns |
|---|---|
| `cloud-itonami-crowdfunding-campaign` | admission, launch, suspension |
| `cloud-itonami-crowdfunding-pledge` | pledge intake, change, cancellation |
| `cloud-itonami-crowdfunding-collection` | charging backers at the deadline |
| `cloud-itonami-crowdfunding-payout` | releasing money to creators |

## Units and time

Amounts are **integer minor units** of the campaign currency (yen,
cents) — never floats, the `kotoba.reji` discipline. Timestamps are
ISO-8601 UTC strings, so lexicographic compare is chronological
compare; the library has no clock and every function that needs "now"
takes it as an argument.

## Test

```bash
kbb -M:test     # 134 tests, 426 assertions
kbb -M:lint
```

## Licence

AGPL-3.0-or-later.
