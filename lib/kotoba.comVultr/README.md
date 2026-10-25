# com-vultr

Portable (`.cljc`) Vultr API v2 client -- account balance, billing
history/invoices, and compute instance listing, read-focused with one
tested auth/HTTP boundary and an injectable transport, for any
kotoba-lang/gftdcojp project that needs to check Vultr account/billing
state instead of re-deriving `curl`/HTTP-call boilerplate ad hoc.

## Why this exists

A 2026-07-06 mail-triage pass over jun784@gmail.com surfaced a recurring
Vultr invoice (~$700-900/month) alongside a stale note-to-self from three
weeks earlier that still wanted a cost inventory ("棚卸し") of the account
before deciding what to cut. Answering "what is this account actually
running, and what did it actually get billed for" today means opening the
Vultr dashboard by hand or trusting an invoice email's subject line. A
portable client that can answer that from the API itself is the same kind
of capability `com-cloudflare` gives for "what actually serves this
hostname", or `com-wise` for "what state is this transfer actually in".

**This library cannot toggle auto-pay / auto-renewal.** Vultr's API v2
does not expose that setting -- it is dashboard-only. Disabling auto-pay
stays a manual (or browser-automation-driven) dashboard action; this
library only answers the "what's running and what did it cost" half of
the cost-review question.

## Design

```text
vultr.client    -- auth (Bearer API key) + HTTP (injectable :http-fn) + JSON envelope
vultr.account   -- get-account: balance / pending charges / last payment
vultr.billing   -- list-history, list-invoices, get-invoice, invoice-items
vultr.instances -- list-instances, get-instance (label/tag/region filters)
```

Query construction and response parsing are pure `.cljc`. The actual HTTP
call is JVM-only by default (`java.net.http`) but every function takes an
injectable `:http-fn` (`{:url :method :headers :body} -> {:status :body}`,
the same convention `cloudflare.client`/`gmail.client`/`wise.client`
already use) -- every namespace here is tested with a stub, never only
against a live account. Vultr has no public sandbox API (unlike Wise), so
there is only one `api-base`.

**Out of scope, deliberately**: starting/stopping/reinstalling/deleting an
instance, changing a plan, or toggling auto-pay (the last one isn't even
possible via the API -- see above). Per this org's risk-gate convention
(`kotoba-issue-clj`'s risk tiers, `local-manimani` ADR-0019, and
`com-wise`'s same stance on money movement), `:financial`/`:destructive`
actions always need a human-approved gate, not a library call. This client
stays read-focused so it can't itself become that gate.

## Usage

```clojure
(require '[vultr.account :as account]
         '[vultr.billing :as billing]
         '[vultr.instances :as instances])

;; VULTR_API_KEY in the environment, or pass :token explicitly
(account/get-account)
;; => {:balance -812.40 :pending_charges 0 :last_payment_date "2026-07-01T..." ...}

(instances/list-instances {:tag "prod"})
;; => [{:id "abc" :label "web-1" :plan "vc2-4c-8gb" :region "nrt" :status "active" ...} ...]

(billing/list-invoices {:per-page 12})
;; => [{:id 123 :date "2026-07-01" :amount -387.28 ...} ...]

(billing/invoice-items 123)
;; => [{:description "vc2-4c-8gb" :unit_price -37.20 ...} ...]
```

## Tests

```sh
kbb -M:test
```

No live account required -- every test injects a stub `:http-fn` and
asserts on the request shape.

This is an unofficial, independently-built client; it is not affiliated
with or endorsed by The Constant Company, LLC (Vultr).
