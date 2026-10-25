# ADR-0001: stripe-ops-LLM ⊣ StripeOpsGovernor -- a governed Stripe ops actor

- Status: Accepted (2026-07-24)
- Related: [`com-junkawasaki/root` ADR-2607242700](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607242700-kotoba-lang-stripe-ops-actor.edn)
  (the full cross-repo design record); [`com-junkawasaki/root` ADR-2607161745](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607161745-cloud-itonami-flagship-managed-tier-stripe-billing.edn)
  (the 3 flagship verticals' live Stripe Managed Starter tier this actor targets).

## Context

`orgs/gftdcojp/cloud-itonami` already has 3 live Stripe Payment Links (one
per flagship vertical: cloud-itonami-isic-6399/6310/7810, ADR-2607161745),
but fulfillment is 100% manual (an operator-interest issue gets the link
pasted in by hand). This actor adds a governed, LLM-assistable capability
for that fulfillment step -- read-only Stripe lookups plus creating a NEW
Payment Link against an already-known price -- without touching the
existing checkout/webhook code or granting any write capability beyond
that.

## Decision

Identical shape to every other actor in this fleet (see
`stripe-ops.governor`/`stripe-ops.phase`/`stripe-ops.operation`'s own
docstrings for the full rationale of each HARD check and the single
always-human `:stripe/payment-link-create` actuation). The domain-specific
decisions:

- **Structural scope, not just a governor rule.** There is no `:op` for
  refunds/subscription-mutation/customer-writes/product-price-writes
  anywhere in `operation.cljc` -- adding one later is a code change, not a
  config flip.
- **Known-price whitelist.** `:stripe/payment-link-create` can only
  reference a `price-id` already seeded into the store's `known-prices`
  (ADR-2607161745's 3 real prices, injected by a real caller -- this repo's
  own demo data uses placeholder ids, never the real 1Password-held ones).
- **No custom pricing, ever.** Neither the governor's accepted proposal
  shape nor `stripeport/create-payment-link!`'s own argument list has room
  for a caller-supplied amount/quantity override.
- **Idempotency-Key is a Stripe REQUEST HEADER**, not a body field --
  `live-stripeport` sends it that way; `mock-stripeport` enforces the same
  semantic (same key twice -> same returned record, never a second link).

## Consequences

Same as ADR-2607242700. This repo is the actor library; the integration
into `cloud-itonami.agent`'s ReAct CLI (a tool registration + a thin
projection layer) lives in `orgs/gftdcojp/cloud-itonami` itself.

## Run

```bash
kbb -M:dev:run     # walk a clean lookup + a Payment Link creation + all HARD-hold checks + a phase-0 hold + a backend swap
kbb -M:dev:test    # governor contract · phase invariants · store parity · stripeport request-building
kbb -M:lint        # clj-kondo (errors fail; CI mirrors this)
```
