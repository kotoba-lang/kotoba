# adnet

**First-party ad network / ad-server core — pure Clojure/ClojureScript.**

The advertising twin of the x402 payment stack. Instead of depending on a
third-party ad network (ExoClick) and its fill rate, `adnet` is the pure brain
of **our own** ad network: advertisers bid in **USDC** (settled through the
x402 rail — `kotoba-lang/pay` + `treasury`), publishers (shinshi / isekai /
kotobase / …) run the auction at each placement to pick the winning creative,
and a first-party **house ad** backfills when no paid campaign qualifies. So ad
income flows in our own currency instead of a vendor's payout.

Same invariants as the rest of the monetization stack (`pay` / `treasury`):
**pure `.cljc`, zero network I/O, zero deps.** The host injects storage, the
clock, and USDC settlement; this library only decides which ad wins and what it
costs. Distinct from `kotoba-lang/senden` (which measures *your own* marketing
campaigns/funnels) — `adnet` *serves third-party ads* with auction + billing.

## `adnet.core` — auction & serving

- **model** — a campaign carries `{:creative :bid{:model :cpm|:cpc :usd} :targeting{:tier :formats :placements :geo} :budget :flight :status}`.
- `eligible?` — tier / format / placement / geo match, in flight, active, budget left.
- `ecpm-micros` / `select` — the auction: rank eligible campaigns on effective
  CPM (CPC normalized by an assumed CTR), highest wins.
- `serve` — the serve decision: `{:kind :paid :campaign … :creative …}` or the
  `house-ad` backfill (which promotes the x402 catalog + creator support).
- `apply-spend` / `reset-daily` — pure budget/pacing transitions (auto-pause on
  exhaustion).

## `adnet.billing` — USDC charges over x402

- `charge-micros` — an impression on a CPM campaign costs `bid/1000`; a click on
  a CPC campaign costs the full bid; cross cases are free.
- `accrue` — fold an event into a campaign (charge + advance budget + emit an
  append-only ad-event record).
- `balance-micros` / `low-balance?` — prepaid accounting: advertisers pre-fund a
  campaign with a USDC deposit (verified via `treasury/receipt->onchain`);
  impressions/clicks draw it down (no per-event on-chain tx — gas would dwarf a
  $0.002 impression); the host prompts an **x402 top-up** when the balance runs
  low. Settlement is periodic accrual, not per-impression.

## `adnet.entitlement` — ad-funded service (a free tier paid for by advertisers)

The join `core` and `billing` deliberately do not make: an impression's charge
becomes an entitlement to run one metered unit of a service, so a publisher can
give the service away and be paid by the advertiser instead of the user.
`murakumo.cloud`'s free inference lane is the first caller.

- `admit-impression` — the verdict for one served-and-viewed impression:
  credit in micros, who funded it, and the viewer's new balance. Refuses, with
  a named reason, on the four ways an ad-funded tier leaks: the **house
  backfill** (unsold inventory funds nothing), the **unbillable impression**
  (`charge-micros` is 0 for an impression on a CPC campaign, so a *paid* serve
  is not evidence of revenue), the **replayed view** (the caller must present
  a receipt it already consumed — "cannot say" refuses), and the **sub-unit
  charge** (credit accumulates in micros; it never rounds one impression up to
  one unit).
- `admit-unit` — may this viewer spend balance on one unit now? Admits at
  exactly the unit price; refuses one micro short and says how short.
- `impressions-per-unit` — how many impressions of a campaign pay for one unit,
  **derived** from the bid rather than configured. `nil` (not 0, not a large
  number) when the campaign cannot fund the service at all.
- `funding-mix` — advertiser-funded vs sponsored micros, so a declared house
  sponsorship can never be counted as ad revenue. `:advertiser-share` is `nil`
  with no records rather than 0%.
- A sponsor's `:daily-micros` is a **fleet-wide daily budget**, and
  `admit-impression` requires `:sponsored-micros-today` to enforce it —
  `nil` refuses (`:sponsor/spend-unknown`) rather than reading as an empty
  budget. Without that figure the only bound on house spend is the *per-viewer*
  daily cap, i.e. how many viewers turn up, which is not a bound.
- `self-check` — returns a **count** of failed invariants, not a boolean: a
  boolean cannot separate one regression from a wholly broken build, and this
  file compiles into a Cloudflare Worker.

`:funding-share` is the fraction of ad revenue that funds service rather than
margin. At the default `1` the free tier breaks even against the publisher's
own list price and earns nothing — a deliberate choice, because the marginal
cost of a self-hosted unit is not measured here and this library will not
pretend to know the profit.

## Who uses it

- **Publisher ad-server** (a Cloudflare Worker, follow-up) runs `serve` at each
  placement and records impressions/clicks via `accrue`.
- **cloud-itonami** operates the advertiser-facing campaign management — its
  ops-LLM ⊣ CertGovernor `propose → govern → commit` loop creates/pauses
  campaigns and enforces ad policy (tier segregation, no prohibited content).
- **Sellers** (shinshi …) fall back to this house ad in `ad_slot` before/instead
  of a third-party network.

Design: superproject ADR-2607093500. Apache-2.0.

```bash
kbb -M:test    # 25 tests / 106 assertions
kbb -M:lint
```
