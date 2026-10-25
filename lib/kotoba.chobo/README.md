# chobo

`chobo`（帳簿）is the kotoba-lang shared **services-EC foundation**: the
audit-ledger substrate (EAVT) + subscription/entitlement/metering model +
invoice/settlement + tenant/operator trust. Extracted from itonami's business
model so that **mise** (retail EC: cart/SKU/checkout) and **itonami** (services
EC: subscription/quota/metering/audit) share the same ledger/billing substrate.

Portable `.cljc` (JVM / ClojureScript / SCI / babashka), built on
[`shitsuke`](../shitsuke). Owns no host effects — `ILedgerStore`,
`IInvoiceStore` are injected ports with mock adapters (Datomic/D1/kotoba-server
adapters are follow-ups).

```text
chobo = ledger (EAVT) + subscription (plan/entitlement/quota/metering/overage)
        + invoice (settlement/dunning) + tenant (operator trust)
```

## Boundaries

| layer | role |
|---|---|
| `chobo.ledger` | EAVT activity/artifact/relation/decision/effect + append-only log + `ILedgerStore` |
| `chobo.subscription` | plan/tier/entitlement/quota/metering/overage (from ai-gftd-apex design) |
| `chobo.invoice` | invoice + lines + status statechart + dunning + `IInvoiceStore` |
| `chobo.tenant` | tenant + capabilities + operator trust levels |
| `chobo.events` | re-frame events/subs (portable 7-fn subset via shitsuke) |
| `chobo.views` | pure-hiccup: ledger-entry / meter-gauge / plan-status / invoice-card / tenant-badge |
| `chobo.ssr` | SSR parity via shitsuke.hiccup/->html |
| host (mise/itonami) | projects domain events → ledger activities; injects store impls |

## Relation to mise + itonami

- **mise** (retail): `mise.order` → `chobo.ledger` activity (via
  `mise.ledger` projection stub); `mise.pricing` totals → `chobo.invoice` line.
- **itonami** (services): its EAVT schema (`:itonami.activity/...`) is the
  origin; chobo.ledger is the portable extraction. itonami's subscription lanes
  map onto `chobo.subscription`.

## Tests

```bash
kbb -M:test            # published git shitsuke dep
kbb -M:local:test      # local ../shitsuke override
```

## Design

See `docs/design.md` and `docs/adr/0001-chobo-services-ec.md`.
