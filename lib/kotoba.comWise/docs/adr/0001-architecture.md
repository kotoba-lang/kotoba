# ADR-0001 — com-wise architecture: a portable, read-focused Wise API boundary

- Status: Accepted
- Date: 2026-07-06
- Context tags: wise-api, portable-cljc, vendor-client, risk-gate
- Builds on: `kotoba-lang/com-cloudflare` (client/`:http-fn` injection
  pattern), `kotoba-lang/kotoba-issue-clj` (risk-tier vocabulary this
  library's non-goals defer to)

## Decision

Give the Wise Platform API the same treatment `com-cloudflare` gave
Cloudflare: one tested `client` namespace (auth + HTTP + JSON envelope,
injectable `:http-fn`, sandbox/production base switch) plus one namespace
per capability area (`profiles`, `transfers`, `quotes`, `recipients`,
`balances`), pure `.cljc` except the JVM-only default transport.

## Why read-focused, not a full transfer-execution client

Wise moves real money. `gftdcojp/local-manimani`'s ADR-0019 (risk gate) and
`kotoba-lang/kotoba-issue-clj`'s risk tiers both establish the same
invariant: `:financial`/`:destructive` actions always route through a
human-approved gate, never execute directly from a library call or an
agent's own judgment. Implementing "create and fund a transfer" here would
make this client itself the thing that needs gating, so that surface is a
deliberate non-goal -- `wise.quotes/create-quote!` stops at a quote (no
funds move; it's the read-adjacent step needed to show a human what a
transfer would cost before they approve one elsewhere).

## Module boundaries

```
client     auth (Bearer API token) + HTTP (injectable :http-fn) + JSON envelope, sandbox/production base
profiles   list profiles, pick the business-typed one
transfers  list (profile + optional status)/get -- transfer state, read-only
quotes     create-quote! -- source/target currency + amount -> fees/rate, commits nothing
recipients list recipient accounts for a profile
balances   list multi-currency balances for a profile
```

## Non-goals

- Transfer execution, cancellation, or any other irreversible/external-send
  write -- see "Why read-focused" above.
- The API token acquisition flow itself -- callers supply
  `WISE_API_TOKEN` (env) or an explicit `:token`, mirroring
  `cloudflare.client`'s `CLOUDFLARE_API_TOKEN` convention.

## Consequences

- `kotoba-lang/kotoba-procedure-clj` procedures that track a Wise KYC/
  account-setup process (a deadline + whose-turn-is-it state) can query
  real transfer/profile state through this library instead of trusting an
  email's prose, without this library ever becoming able to move money on
  its own.
- Adding transfer execution later is possible but must go through this
  org's risk-gate convention at the call site, not be added silently to
  this client.
