# kotoba-retail

[![CI](https://github.com/kotoba-lang/retail/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/retail/actions/workflows/ci.yml)

**Retail SKUs, EAN-13 barcodes, POS receipts and inventory in pure Clojure.**
A [kotoba-lang](https://github.com/kotoba-lang) capability library for the
[`cloud-itonami-4711`](https://github.com/gftdcojp/cloud-itonami-4711)
community-retail open business: SKU records, EAN-13 (GS1) article numbers
with mod-10 checksum validation, POS line items and receipts, and inventory
stock records with reorder thresholds.

No network, no I/O. Amounts are plain numbers in the smallest currency unit.
Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM.


## Maturity

| | |
|---|---|
| Role | capability |
| Tests | JVM 51 assertions + cljs 24 checks, all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.retail :as retail])

(retail/ean13-valid? "4006381333931")          ; => true
(retail/sku "S1" :name "Widget" :price 200)
(retail/needs-reorder? (retail/inventory "S1" "L1" 3 :reorder-at 5)) ; => true
(retail/receipt "R1" [(retail/line-item "S1" 200 2)])
```

## Operator console (UI/UX)

A read-only HTML dashboard renders inventory (with reorder warnings) and receipts for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`)
— writes stay behind the governor.

```clojure
(require '[kotoba.retail.ui :as ui])

(ui/dashboard
  {:inventories [(ret/inventory "S1" "L1" 3 :reorder-at 5)]
   :receipts [(ret/receipt "R1" [(ret/line-item "S1" 200 2)])]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (quote/backslash/newline
escaped) for inventory (reorder flag) and receipts.

```clojure
(require '[kotoba.retail.export :as ex])

(ex/inventory->csv inventories)   ; flags reorder
(ex/receipts->csv receipts)     ; net/tax/total
(ex/inventory->json inventories)
```

## License

Apache License 2.0.

## Test

Two runtimes, because the portability claim above is part of the contract.

```bash
kbb -M:test                          # JVM  — 15 tests / 51 assertions
kbb --backend sci --classpath src test/nbb_smoke.cljk  # cljs — 24 checks, must agree with the JVM
```

The cljs run recomputes the values the JVM suite pins rather than only loading
the namespaces, so a host-interop divergence (`Math/round`, `int`/`char`
arithmetic, regex, `str/escape`) shows up as a disagreement between runtimes.
It exits `0` when it agreed, `1` when it disagreed and names the check, and `2`
when it could not measure — "could not measure" must not leave the same trace
as "measured and fine".

`kotoba.retail.ui` is **not** covered by the cljs run: it requires `html.core`
and `css.core`, which nbb has no classpath for here. Its portability is
unmeasured, not verified.
