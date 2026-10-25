# madoguchi

`madoguchi`（窓口）— kotoba-lang shared **customer support / CRM** domain
library: tickets (SLA, status statechart), customers (tags, LTV, contact log).
Portable .cljc on [`chobo.ledger`](../chobo) (lane `:support`) +
[`shitsuke`](../shitsuke). Zero host effects.

| layer | role |
|---|---|
| `madoguchi.ticket` | Ticket + status statechart (new→open→pending→resolved→closed, reopen) + SLA breach + ledger projection |
| `madoguchi.customer` | Customer + tags + LTV + order refs + contact log |
| `madoguchi.events` | re-frame events/subs (portable 7-fn subset) |
| `madoguchi.views` | pure-hiccup: ticket-row, customer-card |
| `madoguchi.ssr` | SSR parity |

```bash
kbb -M:test       # published deps
kbb -M:local:test # local ../shitsuke ../chobo
```

See `docs/design.md` and `docs/adr/0001-madoguchi-support-crm.md`.
