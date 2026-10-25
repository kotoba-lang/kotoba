# kotoba-itinerary

[![CI](https://github.com/kotoba-lang/itinerary/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/itinerary/actions/workflows/ci.yml)

**Scheduled legs, connection legality and itinerary construction in pure
Clojure.** A [kotoba-lang](https://github.com/kotoba-lang) capability
library for the journey-planning half of a flight fare search. Portable
`.cljc` (JVM / ClojureScript / SCI / GraalVM), no network, no I/O, no
ambient clock, zero dependencies.

Pairs with [`kotoba-lang/fare`](https://github.com/kotoba-lang/fare),
which prices what this builds.

## Why this exists

[`kotoba-lang/reservation`](https://github.com/kotoba-lang/reservation)
answers *how many are left to sell* and *what one operator's own rate
plan charges*, for that operator's own inventory. That is the right
contract for an airline selling its own seats, and it is not enough to
shop for a flight, because shopping starts one question earlier:

> **which sequences of flights actually get someone from A to B, and are
> they legally connectable?**

An itinerary is not just a list of flights that happen to line up on a
map. A connection is legal only if the ground time clears the minimum
connect time published for that airport and carrier pair — 15 minutes at
Narita between two different airlines is a sequence of flights, not an
itinerary. This library builds the ones that connect, and lets a
governor **recompute** the legality of one an advisor proposed.

## The seam that matters

```clojure
(require '[kotoba.itinerary :as it])

(it/violations proposed-itinerary
               {:origin "HND" :destination "SIN" :mct-table our-mcts})
;=> [:below-minimum-connect-time]
```

An advisor can assemble a plausible three-leg itinerary and assert that
it connects. It cannot be trusted to have checked the minimum connect
time at the second stop, and a language model will produce a 20-minute
interline connection at Narita without hesitation. `violations` does the
arithmetic against the same schedule data, so the check is a recompute
rather than a restatement of the claim — the pattern
[ADR-2800002200](https://github.com/com-junkawasaki/root) established for
`cloud-itonami-isic-5110`'s fare and inventory checks.

Every failing check is reported, not the first: an operator fixing a
rejected itinerary should not have to resubmit three times to discover
three problems.

## Usage

```clojure
(require '[kotoba.itinerary :as it])

(defn m [s off] (it/datetime->minutes s off))

(def schedule
  [(it/leg "NH" "841" "HND" "SIN" (m "2026-09-01T11:35" 540) (m "2026-09-01T18:05" 480)
           :classes {"Y" 9} :miles 3312)
   (it/leg "NH" "853" "HND" "TPE" (m "2026-09-01T09:25" 540) (m "2026-09-01T12:25" 480)
           :classes {"Y" 9} :miles 1330)
   (it/leg "BR" "225" "TPE" "SIN" (m "2026-09-01T14:00" 480) (m "2026-09-01T18:45" 480)
           :classes {"Y" 7} :miles 2005)
   ;; departs TPE 15 minutes after NH853 lands -- never offered
   (it/leg "CI" "751" "TPE" "SIN" (m "2026-09-01T12:40" 480) (m "2026-09-01T17:20" 480)
           :classes {"Y" 9} :miles 2005)])

(def mct (it/mct-table {["TPE" :interline] 75 [:default] 60}))

(it/build schedule {:origin "HND" :destination "SIN" :mct-table mct})
;=> {:itin/results    [<HND-SIN nonstop, 450 min>
;                      <HND-TPE-SIN via BR225, 620 min>]
;    :itin/found      2
;    :itin/truncated? false
;    :itin/limits     {:max-connections 2 :max-elapsed-minutes 1800 ...}}
```

`:itin/found` is the count **before** the result cap and
`:itin/truncated?` says whether the cap bit. That is not decoration: a
search that silently returns its first 200 hits reads as "this is the
market" when it is not, and the cheapest fare may be on the itinerary
that got cut.

## Design commitments

**Time is integer minutes since the epoch, and always an argument.**
Connection legality is arithmetic on instants, so every leg carries
`:leg/depart-min` and `:leg/arrive-min`. Local wall-clock strings may
ride along for display, but nothing here computes with them. Nothing
reads a clock either — a governor recomputing an itinerary's legality an
hour later must reach the same verdict.

**Construction refuses to build something that lies about itself.**
`leg` returns nil for a flight that arrives before it departs, goes
nowhere, or carries malformed codes; `itinerary` returns nil for an empty
leg list. A search that accepts a backwards leg will happily construct a
journey that arrives before it leaves.

**Bounds are reported, never silent.** `build` returns the limits it
actually applied alongside the results.

**Circles are pruned.** An itinerary that touches the same airport twice
is a circle trip, which prices under different rules than the through
fares such a pool is being searched for.

## What this library does not know

Stated up front, because a shopping engine that quietly guesses at these
is worse than one that refuses:

- **No timezone database.** `datetime->minutes` takes the UTC offset as an
  argument. Deriving "Asia/Tokyo on this date" needs tzdata, which is a
  real dependency with a real update cadence; guessing it from a
  three-letter airport code is how a search sells a connection that does
  not exist.
- **No published MCT table.** `mct-for` is the lookup *structure* for
  minimum connect times — per airport, per carrier pair, online vs
  interline — not the data. Real MCTs are published per
  airport/terminal/carrier-pair and change; an operator supplies their own.
- **No co-terminal knowledge.** HND and NRT are different airports here. A
  caller who wants them treated as one origin runs `build` once per
  airport and concatenates.
- **No mileage or distance data.** Legs carry `:leg/miles` if the caller
  supplies it; nothing here computes a great-circle distance.
- **No availability authority.** `:leg/classes` is what the schedule
  claims. An operator's own inventory is authoritative in
  `kotoba-lang/reservation`.

## Tests

```
kbb -M:test    # 19 tests, 105 assertions
kbb -M:lint
```

## License

Apache-2.0.
