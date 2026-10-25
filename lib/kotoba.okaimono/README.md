# kotoba-okaimono

[![CI](https://github.com/kotoba-lang/okaimono/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/okaimono/actions/workflows/ci.yml)

**Shopping orders (お買い物), line items and the order lifecycle in pure
Clojure.** A [kotoba-lang](https://github.com/kotoba-lang) capability
library for the
[`cloud-itonami-isic-5320`](https://github.com/cloud-itonami/cloud-itonami-isic-5320)
community last-mile courier open business: order records with line items
and totals, an explicit status-transition table, COD flags, and the
single `dispatchable?` question a courier governor asks before a
delivery may be dispatched.

No network, no I/O. Portable `.cljc` across JVM / ClojureScript / SCI /
GraalVM.

See ADR-2607121900 (com-junkawasaki/root) for the design decision this
library is part of (Shippify-class last-mile delivery, replaced by an
open, governed courier actor).

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 45 assertions, all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.okaimono :as ok])

(def lines [(ok/line "sku-1" "Coffee beans 200g" 2 900)
            (ok/line "sku-2" "Mug" 1 1200)])

(def o (ok/order "ok-1" "st-1" {:name "Tanaka" :address "2-2 Yanaka"} lines :cod? true))

(ok/total o)                 ; => 3000
(ok/item-count o)            ; => 3
(ok/advance o :confirmed)    ; explicit transition table; illegal → nil
(ok/dispatchable? o)         ; => false (only :packed dispatches)
```

Lifecycle: `:placed → :confirmed → :packed → :handed-over → :delivered`,
with `:cancelled` reachable until hand-over (a parcel already with the
courier can no longer be cancelled). `dispatchable?` is the single
question the `cloud-itonami-isic-5320` Courier Governor asks before a
delivery dispatch may proceed: only a `:packed` order dispatches.

## Operator console (UI/UX)

A read-only HTML dashboard renders orders (status badges, totals, COD and
dispatchability) and line items for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`)
— writes stay behind the governor.

```clojure
(require '[kotoba.okaimono.ui :as ui])

(ui/dashboard {:orders [o] :lines lines})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (quote/backslash/newline
escaped) for orders and line items.

```clojure
(require '[kotoba.okaimono.export :as ex])

(ex/orders->csv orders)
(ex/lines->csv order)
(ex/orders->json orders)
```

## Test

```sh
kbb -M:test
```

## License

Apache License 2.0.
