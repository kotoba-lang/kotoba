# srs

[![CI](https://github.com/kotoba-lang/srs/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/srs/actions/workflows/ci.yml)

**Shared Registry System** — the domain lifecycle a TLD registry runs: allocation,
renewal, transfer, and the Registry Grace Periods of RFC 3915. Pure portable
Clojure (`.cljc`), zero third-party runtime deps, **no clock and no storage**.

This is the part of a registry that is *not* a protocol. [`org-ietf-epp`](https://github.com/kotoba-lang/org-ietf-epp)
is how a command arrives, [`org-ietf-rdap`](https://github.com/kotoba-lang/org-ietf-rdap)
is how the result is published, and [`org-ietf-dns`](https://github.com/kotoba-lang/org-ietf-dns)
is how the delegation is answered on the wire. None of them says what a domain
*does* between those moments — when it auto-renews, how long redemption lasts,
whether a delete on day 4 is a refund and a delete on day 6 is not. That is what
lives here.

It completes the DNS-adjacent stack in this org: [`zone`](https://github.com/kotoba-lang/zone)
models zone files, [`godaddy-dns`](https://github.com/kotoba-lang/godaddy-dns)
talks to *someone else's* registrar API, `org-ietf-dns` answers queries. `srs`
is the piece that decides who holds the name in the first place.

## Why no clock

Every function takes `now` as an epoch-millisecond argument. Nothing here reads
a system clock, sleeps, or schedules.

That is not purity for its own sake. The interesting transitions in a domain's
life are 30 to 45 days apart — redemption ending, the auto-renew grace closing,
a transfer auto-approving on day 5. A registry that reads the clock can only
test those by waiting or by mocking time, so in practice nobody tests them, and
the code that deletes domains is the least exercised code in the system. Here a
decade is an ordinary expression:

```clojure
(lc/advance domain policy (t/plus-years t0 6))
;; => 6 :domain/auto-renewed events, expiry seven years out
```

The whole 30-day redemption sequence, the 60-day transfer lock, and the AGP
refund boundary are each a one-line assertion. See `test/srs/lifecycle_test.cljk`.

## The phases

```
available ──create──▶ active ──delete──▶ redemption ──▶ pendingDelete ──▶ purged
                        ▲                    │                              │
                        └────restore─────────┘                              ▼
                                                                        available
```

Grace periods **overlay** `active` rather than replacing it (RFC 3915 §3.1): a
domain in `addPeriod` is an ordinary active domain that happens to be
refundable, and a domain can be in `renewPeriod` and `transferPeriod` at once.
Modeling them as phases — which the RFC's flat status list invites — makes them
mutually exclusive, and they are not.

## Usage

```clojure
(require '[srs.core :as srs] '[srs.time :as t])

(def reg (srs/empty-registry "com"))

(def r (srs/execute reg {:command/kind :domain/create
                         :command/name "example.com"
                         :command/registrar "reg-a"
                         :registrant "alice"
                         :years 2
                         :nameservers ["ns1.example.net"]
                         :auth-info "hunter2"}
                    now))

(:events r)
;; => [{:event/kind :domain/created :event/domain "example.com"
;;      :event/years 2 :event/billable :create :event/expires-at …}]

(srs/info (:registry r) "example.com" now)
;; => {:domain/name "example.com" :domain/statuses #{:addPeriod} …}   ; no authInfo

(srs/zone-records (:registry r) now)
;; => [{:name "example.com" :nameservers ["ns1.example.net"]}]
```

`execute` returns `{:ok? true :registry … :domain … :events […]}` or
`{:ok? false :error {:error/code 2304 :error/message "…"}}`. A failed command
returns the error **and nothing else** — no partially-updated registry escapes,
so a caller cannot commit half of one.

## Events, not effects

A create is also a line on an invoice, a delegation to publish, and an RDAP
record that changed. `srs` returns those as data instead of performing them:

| event | consumed by |
|---|---|
| `:domain/created` `:domain/renewed` `:domain/auto-renewed` `:domain/transferred` | `domain-billing` (each carries `:event/billable`) |
| `:domain/deleted` | billing — `:event/refundable?` and `:event/within-grace` decide the refund |
| `:domain/created` `:domain/updated` `:domain/purged` | the zone publisher, via `zone-records` |

The dependency points one way. `domain-billing` reads `srs`; `srs` reads
nothing.

## Decisions worth knowing about

**`curExpDate` is required on renew.** RFC 5731 §3.2.3 makes it mandatory and
it reads as pedantry until it happens: a registrar retrying a renew it never saw
acknowledged, against a registry that already applied it, renews twice and bills
the registrant twice. Matching the caller's view of the expiry against the
registry's turns that retry into an error instead of a second year. Passing
`nil` skips the check — a choice the caller has to make explicitly.

**Statuses carry their own prohibitions.** `srs.status/prohibits` maps each EPP
status to the operations it blocks, so `blocked-ops` is the only place that
knowledge lives. A registry that stores statuses as opaque strings re-implements
the policy at every call site, and the call sites drift.

**`client*` and `server*` are not interchangeable.** Same prohibition, different
authority: a registrar can clear its own locks and cannot clear the registry's.
`update` refuses any attempt on a `server*` status — that asymmetry is the only
thing a registry lock *is*.

**`ok` is derived, never stored.** RFC 5731 §2.3 defines it as the value an
object carries when it has no other status. A stored `ok` alongside a
prohibition reports a locked domain as unlocked to anyone who checks for `ok`
rather than for the absence of locks.

**Calendar arithmetic is real.** A domain created 2024-02-29 for one year
expires 2025-02-28. Approximating a year as 365 days puts the expiry on the
wrong day for every term spanning a leap day, and over a 10-year term silently
gifts two. `srs.time` implements proleptic Gregorian civil-date conversion in
integer math rather than reaching for `java.time` (JVM-only) or `js/Date`
(CLJS-only, local-zone by default), so the same term means the same date on
every host.

**Names are normalized once, on the way in.** `EXAMPLE.com` and `example.com.`
are one object. Comparing unnormalized forms is exactly the defect recorded in
[ADR-2607262100](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607262100-dns-name-normalization-and-dead-tests.edn),
where FQDN and zone-relative spellings were compared directly and every DNS
record silently classified as a safe addition.

**Multi-label suffixes work.** `in-namespace?` is written against the registry's
own TLD set, not by counting labels. A registry for `co.jp` serves
`example.co.jp`; counting to two would have refused every ccTLD second-level
registry.

## Hosts: in-zone versus out-of-zone

`srs.host` exists because two questions cannot be answered by strings:

**Is this nameserver still in use?** A host any domain delegates to cannot be
deleted (RFC 5732 §3.2.2). `delete` refuses with **2305** — *object association
prohibits operation*, the code's actual meaning — and names the domains, so a
registrar knows to look for associations rather than for a lock. Associations
are a **set**, not a count: a counter that saw the same domain linked twice
would eventually let a host in use be deleted, or leave an unused one
permanently undeletable.

**Does it need glue?** `ns1.example.com` serving `example.com` is **in-zone**
and MUST carry addresses — resolving it otherwise requires already knowing it,
which is the whole reason glue exists. `ns1.example.net` is **out-of-zone** and
MUST NOT. RFC 5732 §1.1 states both directions and implementations routinely
skip the second: storing an address for a name the registry is not
authoritative for looks helpful and quietly makes the registry an unreliable
second copy of someone else's data. Both directions are enforced, and
`update-addresses` re-checks rather than assuming.

`linked` is a **derived** status, never stored — a stored copy can disagree
with the associations it is supposed to summarize. And `info` reports the
*count*, not the list: which domains use a nameserver is not something a public
response should enumerate.

## Policy

`srs.lifecycle/default-policy` holds gTLD-standard windows — 5-day AGP, 45-day
auto-renew grace, 30-day redemption, 5-day pendingDelete, 5-day transfer
auto-approve, 60-day transfer locks, 10-year maximum term. Every one is policy
rather than protocol; ccTLDs differ widely and an operator is expected to
override by passing a map to `empty-registry`. They are collected in one place
so that no bare number in this library has a provenance you have to guess at.

## Scope

- **In:** domain objects, their lifecycle, statuses, grace periods, transfers,
  the registry-wide sweep, and the projections EPP/RDAP/DNS need.
- **Also in:** host objects (RFC 5732) — `srs.host`. Nameservers as objects
  with their own associations and lifecycle, which is what lets the registry
  answer the two questions plain strings cannot: is this nameserver still in
  use, and does it need glue.
- **Not yet:** contact objects (RFC 5733). Registrant/admin/tech contacts are
  currently opaque handles on the domain. Documented rather than silently
  missing.
- **Never:** storage, a clock, a network, or a price. Prices live in
  `domain-billing`, which reads the events this library returns.

## Test

```
kbb -M:test
```

48 tests / 172 assertions.
