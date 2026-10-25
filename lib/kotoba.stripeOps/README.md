# stripe-ops

A **Stripe operations control plane**: a stripe-ops-LLM ⊣ StripeOpsGovernor
StateGraph that can look up Stripe objects (customers/subscriptions/
products/prices) and create **new Payment Links against an already-known,
whitelisted Price** — nothing else. There is no code path anywhere in this
actor for refunds, subscription mutation, customer writes, or product/price
writes; adding one of those later would mean adding a new `:op`, a new
governor branch, and a new commit-effects! branch, not flipping a flag.

Built on this workspace's [`langgraph`](https://github.com/kotoba-lang/langgraph)
StateGraph runtime, the same pattern as [`koyomi`](../koyomi) (schedule-LLM ⊣
ComplianceGovernor) and [`shoko`](../shoko) (drive-LLM ⊣ ACL governor). Here
it is **stripe-ops-LLM ⊣ StripeOpsGovernor**.

> Charter: **(G1)** `:stripe/payment-link-create` is this actor's only
> actuation and is **always a human call** (high-stakes), independent of
> rollout phase — mirrors koyomi's always-human `:event/share`; **(G2)** a
> Payment Link can only ever be created for a `price-id` already in the
> store's `known-prices` whitelist — never one an LLM invents; **(G3)** no
> custom pricing, ever — the only fields a payment-link-create ever carries
> are a known `price-id` + implicit `quantity 1`, structurally, in both the
> governor's checks and `stripeport.create-payment-link!`'s own fixed
> argument list; **(G4)** every write carries a caller-supplied idempotency
> key — a retried/duplicate approval can never create a second live
> Payment Link; **(G5)** `:stripe/lookup` (read-only) has no external write
> effect and may auto-commit at higher phases — it is not this actor's
> actuation.

## The core contract

```
                                    ┌─────────────────────┐
  :stripe/lookup                    │ StripeOpsGovernor    │  (independent system)
  :stripe/payment-link-create  ───▶ │  known-price ·        │
  (stripe-ops-LLM, sealed)          │  idempotency-key ·    │
                                    │  no-custom-amount      │
                                    └──────────┬───────────┘
                       commit ◀─────────────────┼────────────▶ hold (unknown price /
                (lookup: read-only,        escalate                missing idempotency-
                 auto ok at phase≥2;            │                  key / custom amount /
                 payment-link-create:            ▼                  unrecognized op —
                 ALWAYS here) ──────────▶   human sign-off          un-overridable)
                                            (payment-link-create
                                             is ALWAYS high-stakes,
                                             any phase)
```

## Files

- `stripeport.cljc` — the ONE place a real Stripe API call leaves the
  building. `mock-stripeport` (default) is a deterministic in-memory target
  with idempotency-aware Payment Link creation — nothing here ever touches
  a network. `live-stripeport` is an opt-in real transport (Stripe's REST
  API via plain HTTP, no `stripe` SDK — matches `cloud-itonami.edge.billing`'s
  own zero-dependency convention); `:api-key`/`:http-fn` are always
  constructor-injected, never hardcoded or env-guessed inside this library.
- `governor.cljc` — the independent censor (see charter above).
- `phase.cljc` — 0→3 staged rollout, gating only `:stripe/lookup`'s
  autonomy; `:stripe/payment-link-create` is never in any phase's `:auto`
  set.
- `store.cljc` — `Store` protocol, `MemStore` (default) ‖ `DatomicStore`
  (via `langchain.db`). Demo `known-prices` are **placeholder ids**, not the
  real Stripe Price ids ADR-2607161745 created for cloud-itonami-isic-6399/
  6310/7810 (those live in 1Password) — a real integration seeds the real
  ids via `seed!`.
- `advisor.cljc` — `mock-advisor` (default, mechanical pass-through +
  store-grounded confidence) and a swappable `llm-advisor` seam (unused by
  default).
- `operation.cljc` — the langgraph-clj StateGraph:
  `intake → advise → govern → decide → commit | hold | approval`.
- `sim.cljc` — runnable demo (`kbb -M:dev:run`).

```bash
kbb -M:dev:run     # clean lookup + a Payment Link creation + all HARD-hold checks + a phase-0 hold + a DatomicStore backend swap
kbb -M:dev:test    # governor contract · phase invariants · store parity · stripeport request-building
kbb -M:lint        # clj-kondo (errors fail; CI mirrors this)
```

`kbb -M:dev:run` and the test suite always use `mock-stripeport` — no
live Stripe API call happens anywhere in this repo, including its test
suite.

## Restricted Stripe API key (owner setup required)

`live-stripeport` needs an `:api-key`. **This repo does not create one and
ships no value for it** — provisioning a credential is a human, Dashboard
form-filling action outside this actor's scope (ADR-2607242700). To wire up
the real integration, the owner should create a Stripe Dashboard
**restricted key** scoped to:

- Customers — **read**
- Subscriptions — **read**
- Products — **read**
- Prices — **read**
- Payment Links — **write** only

No other permission. This is deliberately a *separate* key from
`STRIPE_SECRET_KEY` (the fuller-permission key `cloud_itonami.edge.billing`
already uses for checkout-session creation) — so even a bug in this actor's
governor logic cannot physically reach a refund/subscription-mutation/
product-price-write call, because the credential itself cannot perform
those calls. Store the resulting key the same way `STRIPE_SECRET_KEY` is
already stored (1Password + the relevant Cloudflare/CLI secret binding),
under the name `STRIPE_OPS_RESTRICTED_KEY`. Until this key exists, any
caller wiring this actor up should keep using `mock-stripeport` — it is
fully offline and safe by default.

## Design rationale

See [ADR-2607242700](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607242700-kotoba-lang-stripe-ops-actor.edn)
in `com-junkawasaki/root` for the full design record (why a new actor
rather than the literal `@stripe/agent-toolkit` npm package, why a new repo
rather than extending `cloud-itonami.ops_governor`, and the ADR this
targets: [ADR-2607161745](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607161745-cloud-itonami-flagship-managed-tier-stripe-billing.edn),
the 3 flagship verticals' live Stripe Managed Starter tier). Repo-local
record: [`docs/adr/0001-stripe-ops-actor.md`](docs/adr/0001-stripe-ops-actor.md).
