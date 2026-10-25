# com-wise

Portable (`.cljc`) Wise (formerly TransferWise) Platform API client --
profiles, transfers, quotes, recipient accounts, and multi-currency
balances, read-focused with one tested auth/HTTP boundary and an injectable
transport, for any kotoba-lang/gftdcojp project that needs to check Wise
transfer/account state instead of re-deriving `curl`/HTTP-call boilerplate
ad hoc.

## Why this exists

Tracking down "what state is this Wise transfer/account actually in" today
means reading an email and trusting its prose, or logging into wise.com by
hand. A portable client that can answer "what does the Wise API itself say
the state is" is the same kind of capability `com-cloudflare` gives for
"what actually serves this hostname" -- a real, reusable answer instead of
an ad hoc one-off. This library pairs with `kotoba-lang/kotoba-procedure-clj`
for tracking multi-step Wise procedures (KYC, corporate account setup) that
have a deadline and a "whose turn is it" state, and with
`kotoba-lang/com-gmail` for the Gmail side of the same workflow.

## Design

```text
wise.client     -- auth (Bearer API token) + HTTP (injectable :http-fn) + JSON envelope
wise.profiles   -- list profiles, pick the business-typed one
wise.transfers  -- list (by profile + optional status)/get transfer state
wise.quotes     -- create a quote (source/target currency + amount -> fees/rate)
wise.recipients -- list recipient accounts for a profile
wise.balances   -- list multi-currency balances for a profile
```

Query construction and response parsing are pure `.cljc`. The actual HTTP
call is JVM-only by default (`java.net.http`) but every function takes an
injectable `:http-fn` (`{:url :method :headers :body} -> {:status :body}`,
the same convention `cloudflare.client`/`gmail.client` already use) --
every namespace here is tested with a stub, never only against a live
account. Pass `:api-base wise.client/sandbox-api-base` to hit Wise's sandbox
instead of production.

**Out of scope, deliberately**: executing a transfer from a quote,
cancelling a transfer, or any other irreversible/external-facing write.
Wise moves real money; per this org's risk-gate convention (see
`kotoba-lang/kotoba-issue-clj`'s risk tiers and ADR-0019 in
`gftdcojp/local-manimani`), `:financial`/`:destructive` actions always need
a human-approved gate, not a library call. This client stays read-focused
(plus quote creation, which commits nothing) so it can't itself become that
gate.

## Usage

```clojure
(require '[wise.profiles :as profiles]
         '[wise.transfers :as transfers]
         '[wise.quotes :as quotes])

;; WISE_API_TOKEN in the environment, or pass :token explicitly
(def biz (profiles/business-profile))
;; => {:id 12345 :type "business" ...}

(transfers/list-transfers (:id biz) {:status "incoming_payment_waiting"})
;; => [{:id 9 :status "incoming_payment_waiting" ...} ...]

(quotes/create-quote! (:id biz) {:sourceCurrency "GBP" :targetCurrency "JPY"
                                 :sourceAmount 1000 :payOut "BANK_TRANSFER"})
;; => {:id "quote-id" :rate ... :paymentOptions [...]}
```

## Tests

```sh
kbb -M:test
```

No live account required -- every test injects a stub `:http-fn` and asserts
on the request shape.

This is an unofficial, independently-built client; it is not affiliated
with or endorsed by Wise Payments Limited.
