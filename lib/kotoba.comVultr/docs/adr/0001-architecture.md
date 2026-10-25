# ADR-0001 — com-vultr architecture: a portable, read-focused Vultr API boundary

- Status: Accepted
- Date: 2026-07-06
- Context tags: vultr-api, portable-cljc, vendor-client, risk-gate
- Builds on: `kotoba-lang/com-cloudflare` (client/`:http-fn` injection
  pattern), `kotoba-lang/com-wise` (same read-focused stance, applied to a
  different vendor the same day), `kotoba-lang/kotoba-issue-clj` (risk-tier
  vocabulary this library's non-goals defer to)

## Decision

Give the Vultr API v2 the same treatment `com-cloudflare`/`com-wise` gave
their vendors: one tested `client` namespace (auth + HTTP + JSON envelope,
injectable `:http-fn`) plus one namespace per capability area (`account`,
`billing`, `instances`), pure `.cljc` except the JVM-only default
transport.

## Why read-focused, not a full instance-management client

Vultr instances cost real money per hour and deleting one destroys
whatever state it held. The same invariant `com-wise`'s ADR-0001
established for money transfers applies here for compute
lifecycle: `:financial`/`:destructive` actions (start/stop/reinstall/
delete an instance, change a plan) always route through a human-approved
gate, never execute directly from a library call or an agent's own
judgment. This was not a hypothetical concern -- the same triage session
that motivated this library began with a request to "auto-cancel" Vultr's
billing, and the actual work proceeded only after confirming scope
(auto-pay only, not instance deletion) and getting the owner to drive the
login themselves in a browser. Implementing instance writes here would
make this client itself the thing that needs gating, so that surface is a
deliberate non-goal.

**Auto-pay/auto-renewal is not just excluded by policy -- it isn't in the
API.** Vultr's v2 API has no endpoint for it; it is a dashboard-only
setting. This library's non-goal here is partly a hard API limitation, not
purely a risk-gate choice, and future contributors should not go looking
for an endpoint that does not exist.

## Module boundaries

```
client     auth (Bearer API key) + HTTP (injectable :http-fn) + JSON envelope
account    get-account -- balance / pending charges / last payment, read-only
billing    list-history, list-invoices, get-invoice, invoice-items -- read-only
instances  list-instances (label/tag/region filters), get-instance -- read-only
```

## Non-goals

- Instance lifecycle writes (start/stop/reinstall/delete) or plan changes
  -- see "Why read-focused" above.
- Auto-pay/auto-renewal toggling -- not exposed by Vultr's API at all;
  stays a dashboard (or supervised browser-automation) action.
- The API key acquisition flow itself -- callers supply `VULTR_API_KEY`
  (env) or an explicit `:token`, mirroring `cloudflare.client`'s
  `CLOUDFLARE_API_TOKEN` convention.

## Consequences

- A cost-inventory pass over a Vultr account (which instances are
  running, what they're tagged/labeled, what the last few invoices
  actually billed for) can go through this library's `account`/`billing`/
  `instances` namespaces instead of ad hoc dashboard clicking, the same
  improvement `com-cloudflare`/`com-wise` gave their respective vendors.
- Adding instance-lifecycle writes later is possible but must go through
  this org's risk-gate convention at the call site, not be added silently
  to this client. Adding auto-pay control is not possible without Vultr
  first exposing it via their API.
