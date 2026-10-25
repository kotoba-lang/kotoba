# domain-billing

[![CI](https://github.com/kotoba-lang/domain-billing/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/domain-billing/actions/workflows/ci.yml)

Billing for domain registrations: a price book, and a fold from
[`srs`](https://github.com/kotoba-lang/srs) events to ledger entries and
registrar invoices. Portable `.cljc`, no clock, **no payment**.

`srs` returns events rather than performing effects, and this is the first
consumer of that decision. The dependency points one way: this library reads
`srs` events; `srs` knows nothing about money.

```clojure
(def book (bill/price-book
           {"com" {:create (bill/money 900 "USD")     ; $9.00
                   :renew  (bill/money 900 "USD")
                   :auto-renew (bill/money 900 "USD")
                   :transfer (bill/money 900 "USD")
                   :restore (bill/money 8000 "USD")
                   :icann-fee (bill/money 18 "USD")}}))

(bill/ledger book (:events (srs/execute registry create-cmd now)))
;; => [{:entry/kind :charge :entry/action :create :entry/years 3
;;      :entry/amount    {:money/amount 2754 :money/currency "USD"}
;;      :entry/icann-fee {:money/amount 54   :money/currency "USD"}
;;      :entry/description "New registration — example.com (3 years)"}]
```

## Refund eligibility is never recomputed here

The one thing a billing layer is most tempted to do, and the one thing it must
not. Whether a delete is refundable depends on the RFC 3915 grace periods, and
those are lifecycle policy. `srs.lifecycle/refundable?` already answers it, and
the answer travels on the event as `:event/refundable?` and
`:event/within-grace`.

A billing layer that recomputed it from dates would be a second implementation
of the same rule, free to drift — and the direction it drifts decides whether
registrants get their money back. So `charge-for` reads the event and **never
looks at a date**. The test suite proves it by handing the same instant to two
events with opposite `:event/refundable?` and getting opposite answers.

Which grace period matters, too: an `:auto-renew` grace delete refunds the
*renewal*, not the create. Refunding a create there would hand back a year the
registrar never paid for.

## Money is integer minor units, with its currency attached

Every amount is an integer count of the currency's minor unit — cents for USD,
**whole yen for JPY, which has none**. Floating point cannot represent `0.1`, so
a price book in dollars accumulates error the moment it is summed, and the error
surfaces as an invoice off by a cent for reasons nobody can reconstruct.
`bill/money` refuses a non-integer outright.

`:currency` travels with every amount because a number without one is not a
price. `add` throws on a mismatch rather than summing, and `format-money` uses
the currency's real minor-unit count — formatting ¥3000 as `30.00` is off by a
hundred, and that is the bug a hardcoded `/100` produces.

`scale` is integer-only: there is no such thing as two and a half years of
registration, and a fractional multiplier would reintroduce rounding.

## The ICANN fee is a pass-through, reported separately

Charged per registered year on create, renew, auto-renew and transfer. It is
kept out of the base price because it changes independently of yours, and
reported separately on the invoice because the registry collects and remits it:
reporting only the gross makes the registry's margin look larger than it is and
makes the remittance impossible to reconcile.

## An unpriced action is an entry, not a zero

A TLD or action with no price produces an explicit `:unpriced` entry that
contributes nothing to the total and shows up in `bill/unpriced`. A registry
that silently fails to bill for a TLD it just launched otherwise discovers it at
the end of the month.

## Entries are never coalesced

A registrar's month is a sequence of billable acts. Collapsing two renewals of
the same domain into one line loses the fact that there were two — which is
exactly what a dispute is about. Six years of auto-renewals is six lines.

`by-registrar` takes a `registrar-of` function rather than reading the event,
because sponsorship changes mid-month: the registrar who owed for a renewal is
the one who held the domain **then**, not the one who holds it now.

## What this library does not do

No payment. No card, no wallet, no gateway, no stored credential. It produces
ledger entries and a balance; taking money is a deployment's job and a regulated
one. Keeping the boundary here means this library holds nothing that needs a
vault — which is also why it can be a public `kotoba-lang` library at all.

Also absent: tax and VAT (jurisdiction-specific and not a registry concern
until it is), credit limits and prepayment balances, and any notion of a
registrar's account.

## Test

```
kbb -M:test
```

15 tests / 42 assertions, driven by events from a real `srs` registry rather
than hand-written fixtures.
