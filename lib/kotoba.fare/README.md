# kotoba-fare

[![CI](https://github.com/kotoba-lang/fare/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/fare/actions/workflows/ci.yml)

**Filed fares, fare rules, fare construction and lowest-fare search in
pure Clojure.** A [kotoba-lang](https://github.com/kotoba-lang)
capability library for the pricing half of a flight shopping engine.
Portable `.cljc` (JVM / ClojureScript / SCI / GraalVM), no network, no
I/O, no ambient clock, no floating point, zero dependencies.

Pairs with [`kotoba-lang/itinerary`](https://github.com/kotoba-lang/itinerary),
which builds what this prices.

## Why this exists

Two capability libraries in this fleet already price things, and neither
can price a flight search:

- [`kotoba-lang/reservation`](https://github.com/kotoba-lang/reservation)
  prices **one operator's own rate plan against its own inventory**. That
  is the right contract for an airline selling its own seats.
- `kotoba-lang/pricing-oracle` estimates a **market** price band from
  comparables. It is not a rate engine.

Shopping asks a third question: *given these itineraries and these filed
fares, what is the lowest price that is actually applicable, and why.*
The answer depends on fares that were **not** chosen, on rules that
disqualified them, and on whether splitting the journey into two fare
components beats a single through fare.

## The seam that matters

A language model asked for the cheapest fare will produce a number. It
will be plausible, formatted correctly, and frequently wrong — the
advance-purchase window unchecked, a blackout date ignored, a fare
applied to a carrier that never filed it. This library does not try to
make an advisor better at that. It lets a **governor recompute** the
answer and reject the claim:

```clojure
(require '[kotoba.fare :as f])

(f/price-matches-claim? priced-components opts 68820)   ; is that total the arithmetic?
(f/fare-applies?        fare ctx)                        ; is this fare even eligible?
(f/no-cheaper-than?     itineraries fares opts 98000)    ; did anything beat that quote?
(f/cheapest-matches-claim? itineraries fares opts 68820) ; is "cheapest" actually cheapest?
```

The last two are the ones that do not exist anywhere else in this fleet.
`kotoba.reservation/quote-matches-claim?` verifies a price against **one**
rate plan. Verifying a *shopping* claim means re-running the search,
because "this is the lowest fare" is a statement about every fare that
was not chosen.

`no-cheaper-than?` and `cheapest-matches-claim?` are deliberately
different checks. An advisor quoting **above** the true minimum passes
the first and fails the second — nothing beat its own quote, but it is
still overcharging.

## Usage

```clojure
(require '[kotoba.fare :as f] '[kotoba.itinerary :as it])

(def fares
  [(f/fare "YOWSIN"  "NH" "HND" "SIN" "Y" :amount 98000 :currency "JPY")
   (f/fare "VLXAP21" "NH" "HND" "SIN" "Y" :amount 61000 :currency "JPY"
           :rules (f/rules :advance-days 21 :min-stay-days 3))
   (f/fare "YOWTPE"  "NH" "HND" "TPE" "Y" :amount 44000 :currency "JPY")
   (f/fare "YOWSGN"  "BR" "TPE" "SIN" "Y" :amount 39000 :currency "JPY")])

;; The derived date facts come from kotoba.itinerary's pure functions, so
;; advisor and governor cannot disagree about what day it was.
(def ctx {:travel-date  "2026-09-01"
          :weekday      (it/weekday-of "2026-09-01")           ; 2, a Tuesday
          :advance-days (it/days-between "2026-08-11" "2026-09-01")  ; 21
          :stay-days    7 :sale-date "2026-08-11" :point-of-sale "JP"})

(def opts {:currency "JPY" :ctx ctx
           :surcharges [(f/surcharge "YQ" 7300 :per :segment)]
           :taxes      [(f/tax "SW" :flat 520 :per :itinerary)]})

(f/search itineraries fares opts)
;=> {:search/solutions [{:price/total 68820 :price/base 61000 ... }   ; VLXAP21 nonstop
;                       {:price/total 98120 ... }]                    ; YOWTPE + YOWSGN split
;    :search/found 2 :search/truncated? false
;    :search/unpriceable 0 :search/skipped []}
```

Booked three days out instead of twenty-one, `VLXAP21` simply is not
available and the search falls through to the cheapest fare that **is** —
which is the behaviour a fare engine has to have and a plausible-sounding
answer does not.

`search` compares a single through fare against every way of splitting
the journey into contiguous fare components, and returns the cheapest
per journey. `:search/skipped` names every itinerary too long to
partition; `:search/truncated?` says whether the solution cap bit. Both
exist because a shopping result that quietly omits candidates reads as
"this is the market", and the omitted one may be the cheapest.

## Design commitments

**Integer money, integer basis points, no floats.** Fares filed in a
currency are integers in its minor unit. Fares filed in Neutral Units of
Construction are integers in hundredths of a NUC, converted with an
integer rate of exchange scaled by 10⁴. A total recomputed on another
runtime is bit-identical, which is the entire reason a governor recompute
is worth running.

Truncation is a real decision. IATA's own currency rounding rules round
NUC fares **up** for most currencies; this library truncates, so a
converted fare can only ever land at or below the rounded one. It will
not quietly invent a rounding convention that changes what a passenger is
charged — an operator whose filing requires IATA rounding files in the
currency, and the conversion never runs.

**No clock, and no derived facts.** An advance-purchase check needs to
know how many days lie between the sale and the flight; this library
takes that number as data rather than computing it, exactly the way
`kotoba.reservation/quote-for` takes each date's weekday as data.
`kotoba.itinerary/days-between` and `/weekday-of` are the pure functions
both sides should derive those facts with — one implementation, so a
disagreement about eligibility can never turn out to be a disagreement
about what day it was.

**Unverifiable is not the same as satisfied.** When a fare files a rule
and the fact needed to check it is missing, the fare does **not** apply,
and the violation says so (`:advance-purchase-unverifiable`,
`:day-of-week-unverifiable`, …). Assuming compliance because the input
was incomplete is how a search returns a fare nobody is entitled to.
Same stance ADR-2800002200 took for `cloud-itonami-isic-5110`: a check
that cannot run is a violation, not a pass.

**A partial total is worse than no total.** `price` returns nil when any
component is unpriceable, because a total that silently dropped a
component still looks like a fare. `:pc/amount` is nil for an
inapplicable fare, never 0 — a zero is a price, a nil is a refusal to
state one.

## Fare rules implemented

The ATPCO category each corresponds to, so a reader can tell what is
covered without guessing:

| Category | Rule keys |
|---|---|
| 2 — day/time | `:dow` |
| 3 — seasonality | `:travel-from` `:travel-to` |
| 4 — flight application | `:carriers` (on the fare) |
| 5 — advance reservation/ticketing | `:advance-days` |
| 6 / 7 — minimum / maximum stay | `:min-stay-days` `:max-stay-days` |
| 11 — blackout dates | `:blackout` |
| 15 — sales restrictions | `:sale-from` `:sale-to` `:point-of-sale` |
| 16 — penalties | `:penalty` (carried for **disclosure**, never priced) |

Structural filings — market endpoints, booking class open on every leg,
routing, maximum permitted mileage — are checked by
`fare-matches-component?`.

## What this library does not implement

Named, because a fare engine that quietly omits a category prices tickets
that cannot be issued:

- **Category 10, fare combinability.** Components here price
  *independently*, which is what lets `search` take the cheapest
  applicable fare per component. Real combinability restricts which
  components may sit in one ticket and would invalidate that
  optimization. Not implemented, not approximated — and
  `cheapest-for-partition` names itself as the place the assumption
  breaks if it is ever added.
- **Categories 12 (surcharges), 14 (travel restrictions), 17 (HIP),
  23 (miscellaneous), 25 (fare by rule).** Surcharges are accepted as
  caller-supplied data rather than derived from a filing.
- **Routing maps as graphs.** `:fare/routing` is an ordered list of
  permitted points and a component's intermediates must be a subsequence
  of it. Published routing maps are directed graphs with alternate
  branches, so the subsequence rule accepts a strict subset of what a
  real map permits: it can reject a fare that is genuinely applicable,
  and never accepts one that is not.
- **Ticketing, filing, settlement.** Nothing here files a fare with an
  authority, issues a document, or moves money.

## Tests

```
kbb -M:test    # 26 tests, 165 assertions
kbb -M:lint
```

## License

Apache-2.0.
