# kotoba-securities

[![CI](https://github.com/kotoba-lang/securities/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/securities/actions/workflows/ci.yml)

**Positions, trades and fund shares in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library for the
`cloud-itonami` securities/fund vertical (ISIC 6420 holding companies,
6430 trusts/funds, 6611 market administration, 6612 securities/commodity
brokerage, 6630 fund management): equity-position, trade, fund-share/NAV,
and investment-mandate records.

No network, no I/O, and **no real market data or custody integration** --
an operator supplies their own licensed price feed/custodian; this
library only combines supplied facts (quantity, price, net assets,
outstanding units). Amounts are plain numbers in the smallest currency
unit. Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 37 assertions, all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |
| Reference pricing (optional) | yes (`kotoba.securities.pricing` → `cloud-itonami-isic-6311`) |

## Contract

```clojure
(require '[kotoba.securities :as sec])

(sec/position "P1" "HoldCo" "SUB-A" 1000 :price 5)
(sec/position-value position)                          ; => quantity * price
(sec/trade "T1" "acct-1" "SUB-A" :buy 100 10)
(sec/trade-notional trade)                               ; => quantity * price
(sec/fund-nav "F1" 1000000 100000)                        ; net-assets / outstanding-units
(sec/mandate "M1" "F1" {:max-single-issuer-pct 10})
(sec/breaches-mandate? mandate 15)                        ; => true/false
```

## Operator console (UI/UX)

A read-only HTML dashboard renders positions, trades and fund NAVs for an
operator. Built on [`kotoba-lang/html`](https://github.com/kotoba-lang/html)
(Hiccup→HTML) + [`kotoba-lang/css`](https://github.com/kotoba-lang/css)
(EDN→CSS). Pure data → markup; the console never exposes a write surface
(no `<form>`/`<button>`) -- trade execution, distributions and NAV
publication stay behind the governor.

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (quote/backslash/newline
escaped) for positions and trades.

## Consuming `cloud-itonami-isic-6311` for reference pricing

This library still carries no market data itself, but
[`kotoba.securities.pricing`](src/kotoba/securities/pricing.cljk) is an
optional bridge to
[`cloud-itonami-isic-6311`](https://github.com/cloud-itonami/cloud-itonami-isic-6311)
(the multi-asset market-data actor: MarketData-LLM sealed advisor ⊣
MarketDataGovernor) for operators who want a governed OSS price source
instead of rolling their own. Entirely opt-in — nothing else in this
library requires it, and a deployment that never requires
`kotoba.securities.pricing` runs exactly as before, offline.

```clojure
(require '[kotoba.securities.pricing :as pricing]
         '[marketdata.store :as store]
         '[marketdata.operation :as op])

(def db    (store/seed-db))          ; or a real, operator-configured Store
(def actor (op/build db))
(def ctx   {:actor-id "sub-1" :actor-role :subscriber :tenant "your-tenant"})

(pricing/reference-price actor db "eq-100" ctx)
;; => a price, or nil when the MarketDataGovernor holds the query
;;    (no active contract, a halted/circuit-broken instrument escalating
;;    to a human, etc.) -- never a fabricated fallback price.

(pricing/position-with-market-price actor db "P1" "HoldCo" "eq-100" 1000 ctx)
;; => (sec/position "P1" "HoldCo" "eq-100" 1000 :price <governed price>),
;;    or nil when no governed price is available.
```

The query is the same `:disclosure/query` op any other subscriber would
send — a `tenant`/tier contract is required, over-tier column requests
still hold, halted instruments still escalate to a human. There is no
"internal caller" bypass.

## License

Apache License 2.0.

## Test

```bash
kbb -M:test
```
