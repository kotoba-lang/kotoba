# mise

`mise`（店）is the kotoba-lang shared **e-commerce system**: catalog, pricing,
cart, inventory, checkout, order, and pure-hiccup EC components. A portable
`.cljc` library (JVM / ClojureScript / SCI / babashka) built on
[`shitsuke`](../shitsuke) (the shared UI design system).

The implementation owns no filesystem, network, payment, or persistence effects.
Those are **injected ports** (`IPaymentPort`, `IOrderStore`, `IDiscount`,
`ITax`, `IShipping`) with mock adapters for tests/SSR/dev. Live adapters
(Stripe, D1, B2) are follow-ups.

```text
mise = catalog + pricing + cart + inventory + checkout + order + events + views
```

## Boundaries

| layer | role |
|---|---|
| `mise.catalog` | Product/SKU/Catalog model (EDN) + query fns |
| `mise.pricing` | Price math + totals; `IDiscount`/`ITax`/`IShipping` ports |
| `mise.cart` | Cart line items + invariants (pure) |
| `mise.inventory` | Stock levels + reserve/restock (pure) |
| `mise.checkout` | checkout state machine + `IPaymentPort` (mock adapter) |
| `mise.order` | Order record + status statechart + `IOrderStore` (mock) |
| `mise.events` | re-frame events/subs (portable 7-fn subset via shitsuke) |
| `mise.views` | pure-hiccup EC components on shitsuke.components |
| `mise.ssr` | SSR parity via shitsuke.hiccup/->html |
| host app | payment port / order store impls + side-effects around dispatch |

## Dual render (the contract)

```clojure
(require '[mise.views :as v] '[shitsuke.hiccup :as h])
;; pure hiccup → SSR string:
(h/->html (v/product-card product {:act-add :cart/add}))
;; the SAME hiccup is mounted by reagent in the browser; state via
;; mise.events (shitsuke.re-frame.core, portable subset).
```

## Tests

```bash
kbb -M:test            # published git shitsuke dep
kbb -M:local:test      # local ../shitsuke override (workspace dev)
```

## Design

See `docs/design.md` for the layer-by-layer API and `docs/adr/0001-mise-ec-system.md`
for the decision record.
