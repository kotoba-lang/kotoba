# senden

`senden`（宣伝）— kotoba-lang shared **marketing** domain library: campaigns,
funnel, attribution. Portable .cljc on [`chobo.ledger`](../chobo) (lane
`:marketing`) + [`shitsuke`](../shitsuke). Zero host effects.

| layer | role |
|---|---|
| `senden.campaign` | Campaign + status statechart + spend/conversions/CPA + ledger projection |
| `senden.funnel` | funnel stages (awareness→…→retention) + conversion rates |
| `senden.attribution` | first/last/linear/multi-touch attribution |
| `senden.events` | re-frame events/subs (portable 7-fn subset) |
| `senden.views` | pure-hiccup: campaign-card, funnel-bar |
| `senden.ssr` | SSR parity |

```bash
kbb -M:test       # published deps
kbb -M:local:test # local ../shitsuke ../chobo
```

See `docs/design.md` and `docs/adr/0001-senden-marketing.md`.
