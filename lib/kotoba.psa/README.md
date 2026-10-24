# kotoba-psa

**Professional services in pure Clojure** — staffing, rates, margin,
utilization, invoices. A [kotoba-lang](https://github.com/kotoba-lang) capability
library for the PSA layer (the Kantata / BigTime / Certinia / NetSuite OpenAir /
Deltek Vantagepoint category).

It sits between two siblings and depends on neither:

| library | question |
|---|---|
| [`activity`](https://github.com/kotoba-lang/activity) | how much time was **observed**, and what for |
| **`psa`** | what that time is **worth**, who is committed to what, what may be invoiced |
| [`labor`](https://github.com/kotoba-lang/labor) | what the worker is **paid** |

All three read and emit the same `:ts/*` timesheet shape, so they compose without
any of them depending on the others.

## Maturity

| | |
|---|---|
| Role | capability |
| Dependencies | none |
| Tests | 58 tests, 146 assertions, all green |
| Runtime | `.cljc`, JVM + ClojureScript |
| Actor | `cloud-itonami/tehai` (手配) |

## The four invariants

Each has a test that fails if it stops holding. Every one is a place where PSA
tools conventionally produce a confident number instead of admitting a gap.

**1. No rate, no line.** Time whose `[project role]` has no rate card is reported
as unpriced. It is never billed at zero and never at a "default rate".

```clojure
(psa/price-entry cards (ts "w-1" "2026-01-01" "gamma" :engineer 8))
;; => {:priced/unpriced? true :priced/billable nil ...}
;;                             ^ nil is the absence of a price; 0 would be a price
```

**2. Margin needs both sides.** With a bill rate but no cost rate, margin is
`:unknown` — not equal to revenue. Fake profit is the classic PSA lie and it
comes from exactly this substitution. One uncosted entry is enough to poison
the whole figure, and the count travels with it.

```clojure
(psa/margin priced)
;; => {:margin/revenue 100000 :margin/cost :unknown :margin/amount :unknown
;;     :margin/ratio :unknown :margin/uncosted-count 1}
```

**3. Utilization needs a denominator.** With no declared capacity, utilization is
`:unknown`, not 1.0. A utilization figure is the number people are managed by,
so its denominator does not get invented.

**4. No rate, no conversion.** An amount whose FX rate to the target currency is
unknown is not converted at 1:1 and not dropped — it is excluded from the total
and named, and the total says it is incomplete. See below.

## Contract

```clojure
(require '[kotoba.psa :as psa])

;; Rates. :cost may be omitted — margin then says :unknown rather than
;; pretending the work was free. A role-less card is the project-wide fallback.
(psa/rate-card "alpha" :engineer 15000 :cost 9000)
(psa/rate-card "beta" nil 10000)
(psa/rate-for cards "alpha" :engineer)

;; Staffing. Assignments prorate across a query window, assuming committed
;; hours are spread evenly — a real assumption, stated rather than buried.
(psa/assignment "a-1" "w-1" "alpha" :engineer from to 40)
(psa/capacity "w-1" from to 40)
(psa/allocation assignments capacities "w-1" [from to])
;; => {:allocation/committed-hours 50.0 :allocation/capacity-hours 40
;;     :allocation/capacity-known? true :allocation/over? true ...}
```

An **undeclared** capacity is not an infinite one, and it is not a violation
either: `:allocation/over?` stays false and `:allocation/capacity-known?` says
which case you are in. That is the deliberate difference from invariant 1 —
absent capacity is *unknown*, absent price is a *refusal to guess*.

```clojure
;; Value
(psa/price-entry cards entry)
(psa/margin priced)
(psa/utilization entries capacities "w-1" [from to] date->ms)

;; Invoicing
(psa/invoice "inv-1" "alpha" entries cards billed-key-set)
;; => {:invoice/lines [{:line/role :designer :line/hours 4.0 :line/rate 12000
;;                      :line/amount 48000} ...]
;;     :invoice/total 288000
;;     :invoice/entries [...]           ; the keys this invoice consumed
;;     :invoice/unpriced [...]          ; excluded, no rate card
;;     :invoice/excluded-already-billed [...]}

(psa/describe-gap inv)   ;; "" when nothing was left out
```

Lines are grouped by role, so a project billed at two rates shows two lines
rather than one blended figure nobody can check.

## Tax categories — the grouping, never the rate

A taxing rule does not want lines. 消費税法施行令 第七十条の十 computes the tax
on 「税率の異なるごとに区分して合計した金額」 — the **per-rate subtotal**,
multiplied once and rounded once. Taxing each line and summing the results is a
third method the article does not offer. So the caller must hand its tax library
per-category subtotals, and this is where the lines are.

What this library supplies is the **grouping** and never the rate. It does not
know that `:standard` means 10% anywhere — the category is an opaque keyword it
carries from the rate card to the invoice. A 10% constant in a
jurisdiction-neutral library would be wrong for two of the three continents it
bills on, and wrong for the third the day a rate changes.

```clojure
(psa/rate-card "kappa" :engineer 15000 :cost 9000 :currency "JPY"
               :tax-category :standard)

(psa/invoice "inv-1" "kappa" entries cards)
;; => {:invoice/total 178000
;;     :invoice/lines [{:line/role :caterer :line/tax-category :reduced ...} ...]
;;     :invoice/subtotals-by-tax-category {:standard 168000 :reduced 10000}
;;     :invoice/subtotals-complete? true
;;     :invoice/subtotals-gaps     #{}
;;     :invoice/uncategorised      []
;;     :invoice/subtotals-currency "JPY"
;;     ...}
```

`:invoice/subtotals-by-tax-category` is exactly the shape
`kotoba.taxlaw/consumption-tax-amount` takes as its `:subtotals`.

There is **no project-level default category**, and the argument is in
`rate-card`'s docstring. A role-less card is already the project-wide fallback
for the rate *and* the category together, so a project may declare it once — it
simply does not survive being overridden by an exact-role card. The card that
priced the line is the card that categorises it, so there is one place to look.

**The refusal.** If any contributing rate card declares no category, the
subtotals are not merely incomplete, they are *wrong*: they would sum to less
than `:invoice/total` while looking like a finished map, and a tax library handed
them would round the shortfall into a legal figure. So there is nothing shaped
like an answer to misread —

```clojure
(psa/invoice "inv-1" "kappa" entries cards-with-one-uncategorised)
;; => {:invoice/total 238000                              ; unchanged — the line
;;                                                        ; is billable, just not
;;                                                        ; taxable
;;     :invoice/subtotals-by-tax-category :unknown        ; not a partial map
;;     :invoice/subtotals-complete? false
;;     :invoice/subtotals-gaps     #{:uncategorised-cards}
;;     :invoice/uncategorised      [["kappa" :architect]] ; card-keys, named the
;;     ...}                                               ; way :invoice/unpriced
;;                                                        ; names entries

(psa/describe-tax-gap inv)
;; => "1 rate cards declared no tax category, so no per-category subtotals were stated"
```

None of those requires comparing counts to interpret, and `describe-tax-gap`
returns `""` when there is nothing to say — the same discipline as
`describe-gap`, which is left alone because an uncategorised line *was* billed
and belongs to a different question.

`{}` with `:invoice/subtotals-complete? true` is a real answer: an invoice with
no billable lines owes no tax, and `{}` sums to its total, zero. The subtotals
partition the **lines**, so entries that never became lines are
`:invoice/unpriced`'s business and do not make the subtotals incomplete.

**Currency is checked, not assumed.** One invoice is *not* one currency by
construction: `:invoice/currency` is the first card the caller passed, which need
not be a card the invoice used, and nothing requires a project's cards to agree.
That key is left exactly as it was. The subtotals do not inherit its assumption —
they are refused with `#{:mixed-currency}` when the contributing cards disagree,
and `:invoice/subtotals-currency` states the unit when they do not.

`entry-key` is content-derived — `[worker date project role]` — rather than a
generated id, so the same day's work read from two systems collides on purpose
and a re-imported timesheet cannot be billed twice.

`describe-gap` returns the empty string when nothing was excluded, so a caller
can append it unconditionally without printing a reassuring "no problems" line
that is really "nothing was checked".

## Expenses, subcontractors, revenue and currency

```clojure
;; Expenses. A non-billable expense still counts against margin —
;; absorbing a cost decides who pays, not whether to count it.
(psa/expense "e-1" "alpha" 10000 "USD" :billable? true :markup 0.1)
(psa/expense-billable-amount e)          ;; 11000.0; 0 when non-billable

;; Subcontractors carry BOTH rates explicitly, because a subcontractor's
;; cost is a separate negotiation — inheriting the internal cost rate
;; would report someone else's payroll as this firm's.
(psa/subcontract "s-1" "alpha" "vendor-a" :engineer 10 8000 14000 "USD")

;; Margin across everything a project costs. Invariant 2 is unchanged:
;; one uncosted labour entry and the whole figure is :unknown.
(psa/project-margin priced expenses subs)
;; => {:margin/revenue .. :margin/amount .. :margin/expense-revenue ..
;;     :margin/subcontract-cost ..}
```

**Revenue recognition** — `:as-delivered`, `:percent-complete`, `:on-completion`:

```clojure
(psa/contract "alpha" :percent-complete :fee 1000000 :budget-hours 100)
(psa/recognize contract priced complete?)
;; => {:revenue/amount 400000.0 :revenue/progress 0.4}
```

Percent-complete with no budget returns `:unknown`, not an estimate — "about 80%
done" is a guess and this refuses to supply it. Progress caps at 1.0: an
over-budget project delivered its scope, not 130% of the contract's value, and
the overrun shows up in margin where it belongs.

**A fourth invariant — no rate, no conversion:**

```clojure
(psa/fx-rate "EUR" "USD" 1.08 "2026-01-01")
(psa/convert rates 1000 "EUR" "USD")
;; => {:money/amount 1080.0 :money/rate 1.08 :money/as-of "2026-01-01"}

(psa/total-in rates items "USD")
;; => {:total/amount .. :total/rates-used [..]
;;     :total/unconvertible [..] :total/complete? false}
```

An amount whose rate is unknown is not converted at 1:1 and not dropped: it is
excluded from the total and named, and `:total/complete?` says which you have.
Rates are directional and are **not** inverted automatically — a buy rate is not
a sell rate, and inferring one would invent a spread. Every conversion carries
the rate and the date it came from, because a total that cannot say which rate
it used is a total nobody can check.

## Composing

```clojure
(require '[kotoba.activity :as a] '[kotoba.labor :as labor])

;; observed -> priced
(psa/price-entry cards (assoc (first (a/->timesheet-entries "w-1" date-of att))
                              :ts/role :engineer))

;; observed -> paid
(labor/wages-for contract (a/->timesheet-entries "w-1" date-of att))
```

## Test

```bash
kbb -M:test                                # JVM
kbb --backend sci --classpath src:test test/run_portable.cljk  # the same suite on Node
kbb -M:lint
```

**Mutation testing.** `tools/mutations.edn` covers *only* the tax-category
feature — the rest of the library is not mutated, so a clean run says nothing
about the four invariants above.

```bash
kbb --backend sci tools/check-mutations.cljk   # every :find occurs exactly once
kbb --backend sci tools/mutate.cljk            # 20 mutations; a SURVIVOR is a test gap
```

## License

Apache-2.0.
