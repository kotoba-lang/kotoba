# kotoba-reservation

[![CI](https://github.com/kotoba-lang/reservation/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/reservation/actions/workflows/ci.yml)

**Reservable inventory, holds, rate plans and quotes in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library for the
reservation-bearing [cloud-itonami](https://github.com/cloud-itonami) open
businesses. Portable `.cljc` (JVM / ClojureScript / SCI / GraalVM), no
network, no I/O, no ambient clock.

## Why this exists

Every reservation-bearing vertical in the fleet — passenger air transport
(`cloud-itonami-isic-5110`), accommodation (`-5510`, `-5590`), travel agency
(`-7911`), tour operator (`-7912`), other reservation services (`-7990`) —
needs to answer two questions that no prior kotoba-lang capability library
answered:

- **how many are left to sell?** (`kotoba-lang/retail` models SKUs and stock
  on hand, not dated capacity with holds and authorized overbooking)
- **what does this one cost?** (`kotoba-lang/pricing-oracle` predicts missing
  *market* price bands from comparables; it is not a rate engine)

Without them those actors could log that a booking record existed but could
not check whether the seat was actually available or whether the stated fare
was actually the fare. This library supplies both as pure functions, so an
actor's **governor can independently recompute them** rather than taking its
advisor's word — see `quote-matches-claim?` and `availability-supports?`.

## Design commitments

**Integer money, integer modifiers, no floats.** Amounts are integers in the
currency's minor unit (JPY: 1 = ¥1; USD: 1 = 1 cent). Rate modifiers are
integers in basis points (10000 bp = 100%), applied with truncating integer
division. A quote recomputed on another runtime is bit-identical, which is
the entire reason a governor recompute is worth running.

Truncation rounds toward zero, so a modifier can only ever move a fare *down*
by a sub-unit, never up. An operator whose filed fare rules require different
rounding applies it in their own filing and passes the resulting
`:rate/base-amount`; this library will not pick a rounding convention on
their behalf.

**No clock; calendar only when you ask for it.** `expired?` takes `now`
as an argument, and nothing here ever reads a clock — that one is about
reproducibility, since a governor recomputing minutes later must get the
same answer.

`quote-for` takes each date's weekday as data rather than deriving it,
but *not* for that reason: deriving the weekday of `2026-08-01` is
deterministic and would give the same answer forever. The real reasons
are that the core pricing path should not bake in one calendar system,
and that callers may key modifiers on a fiscal week, a local holiday
table or a season instead. Callers who *do* want proleptic-Gregorian
arithmetic get it explicitly, from `weekday-of` and `nights-between`:

```clojure
(res/nights-between "2026-08-01" "2026-08-05")
;=> [{:date "2026-08-01" :weekday 6} {:date "2026-08-02" :weekday 0}
;    {:date "2026-08-03" :weekday 1} {:date "2026-08-04" :weekday 2}]
;   half-open — a 1st-to-5th stay is FOUR nights, the way accommodation bills
```

That matters for a governor: it recomputes a stay's total from the
booking's **own check-in and check-out**, not from a night list the
advisor supplied and could have shortened.

**Authorized overbooking is a separate field from capacity.** `available`
may legitimately sell into an operator's declared allowance, but `oversold?`
still reports the truth about *physical* capacity. An operator can sell into
their allowance without ever losing track of how far past the aircraft or
the property they have sold.

## Usage

```clojure
(require '[kotoba.reservation :as res])

;; Inventory: one fare class on one flight-date.
(def seats (res/bucket "NH-6" "2026-08-01" :economy 180 :sold 100 :held 20))
(res/available seats)        ;=> 60
(res/sellable? seats 61)     ;=> false — refuses rather than overselling

;; Hold, then confirm. Confirming is the only transition that sells.
(def h (res/hold "h-1" seats 2 "2026-07-27T12:00:00Z"))
(def held (:reservation/bucket (res/place-hold seats h)))
(res/expired? h "2026-07-27T18:00:00Z")   ;=> true — time is passed in
(:reservation/bucket (res/confirm-hold held h))

;; Rate plan and quote.
(def plan (res/rate-plan "Y-FLEX" :economy 42000 "JPY"
                         :advance-days 3
                         :weekday-bp {6 12000}          ; Saturday +20%
                         :date-bp {"2026-08-13" 15000}  ; Obon peak +50%
                         :fees [{:label "airport facility" :amount 2900}]
                         :tax-bp 1000))

(res/quote-for plan {:dates [{:date "2026-08-01" :weekday 6}] :qty 2})
;=> {:quote/subtotal 103700 :quote/tax 10370 :quote/total 114070 ...}

;; The governor seam: recompute rather than trust.
(res/quote-matches-claim? plan {:dates ["2026-09-02"] :qty 1} 49390)  ;=> true
(res/availability-supports? [[seats 2]])                              ;=> true

;; Everything at once, reporting every failure rather than the first.
(res/validate-booking plan {:units 1 :class :economy} [[seats 2]] 49390)
```

## What this library does not do

It does not talk to a GDS, a PSS, a channel manager or a PMS; it does not
file a fare, publish availability, take a payment, or hold any operating
licence. It is the arithmetic an operator's own system needs in order to be
checkable — the integrations and the licence belong to whoever deploys it.

## Namespaces

| ns | purpose |
|---|---|
| `kotoba.reservation` | inventory, holds, rate plans, quotes, verification (zero-dep) |
| `kotoba.reservation.ui` | read-only operator console (kotoba-lang/html + css) |
| `kotoba.reservation.export` | CSV / JSON export for settlement audit |

## Test

```bash
kbb -M:lint
kbb -M:test
```

## License

Apache-2.0.
