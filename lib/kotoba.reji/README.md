# kotoba-reji (レジ)

[![CI](https://github.com/kotoba-lang/reji/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/reji/actions/workflows/ci.yml)

**Count the coins/notes in a cash-register till and work out the smallest
change to hand back — in pure Clojure, across currencies.** Built around a
Japanese *reji* (レジ, cash register): count what's in the drawer, compare it
against expected sales, and hand back exact change. The same two operations
work for any currency with a coin/note denomination table — this ships with
Japan (JPY), India (INR), China (CNY), Brazil (BRL), Mexico (MXN), Saudi
Arabia (SAR) and the UAE (AED).

No network, no I/O, no floating point. Every amount is a plain integer count
of the currency's smallest circulating unit (yen, paisa, fen, centavo,
halala, fils) — money never touches a `double`/`float`, so there's no
binary-decimal rounding error. The core is zero-dependency, all `.cljc`,
portable across JVM / ClojureScript / nbb.

## Contract

```clojure
(require '[kotoba.reji.currency :as currency]
         '[kotoba.reji.core :as core])

;; till-close count: how many of each denomination, what's the total?
(core/tally "JPY" {500 3, 100 12, 10 4})
;; => #:reji.tally{:currency "JPY"
;;                  :lines [#:reji.tally.line{:value 500 :kind :coin :label "¥500" :count 3 :subtotal 1500}
;;                          #:reji.tally.line{:value 100 :kind :coin :label "¥100" :count 12 :subtotal 1200}
;;                          #:reji.tally.line{:value 10 :kind :coin :label "¥10" :count 4 :subtotal 40}]
;;                  :total 2740}

;; compare a count against the register tape's expected sales
(core/till-report "JPY" {500 3, 100 12, 10 4} 2700)
;; => ... :reji.till/expected 2700, :reji.till/difference 40, :reji.till/status :over

;; smallest set of coins/notes for a given amount of change (unlimited supply)
(core/make-change "INR" (currency/parse-amount "INR" "1234.50"))
;; => #:reji.change{:currency "INR" :requested 123450 :given 123450 :remainder 0
;;                   :breakdown [... ₹500 x2, ₹200 x1, ₹20 x1, ₹10 x1, ₹5(coin) x1 minus 50 paise ...]}

(currency/format-amount "INR" 123450)   ; => "₹1,234.50"
(currency/codes)                        ; => ("AED" "BRL" "CNY" "INR" "JPY" "MXN" "SAR")
```

`make-change` returns the *largest exactly-representable* amount below the
requested one (plus `:reji.change/remainder`) instead of throwing, for
amounts that can't be made exactly — e.g. asking MXN for 3 centavos when the
smallest coin is 5.

## Why integer minor units, not decimals

A register that's even one binary-floating-point rounding error off is a
register that doesn't balance at close. Every public function here takes and
returns plain integers in the smallest circulating unit — `500` means ¥500,
`123450` means ₹1,234.50. `currency/parse-amount` and `currency/format-amount`
are the only places decimal strings appear, and both do it with string/int
arithmetic, never `Double`/`Number`.

## CLI

```bash
kbb --backend sci -cp src script/cli.cljk currencies
kbb --backend sci -cp src script/cli.cljk tally JPY 500x3 100x12 10x4
kbb --backend sci -cp src script/cli.cljk change INR 1234.50
```

## Currencies

| Code | Currency | Minor unit | Subdivision |
|---|---|---|---|
| JPY | Japanese Yen | yen | none (`1`) |
| INR | Indian Rupee | paisa | `100` |
| CNY | Chinese Yuan (Renminbi) | fen | `100` |
| BRL | Brazilian Real | centavo | `100` |
| MXN | Mexican Peso | centavo | `100` |
| SAR | Saudi Riyal | halala | `100` |
| AED | UAE Dirham | fils | `100` |

Denomination tables are hand-curated against currently-circulating coins and
notes (`src/kotoba/reji/currency.cljk`) — not a live/authoritative source for
legal tender, and central banks retire/introduce denominations over time.
Adding a currency, including a 3-decimal one (e.g. KWD/BHD/OMR, where
`:reji.currency/subdivision` would be `1000`), is a new table entry — no
other code changes.

## Testing

```bash
kbb -M:test        # JVM, cognitect test-runner
kbb -M:lint         # clj-kondo
```
