# org-ietf-rdap

[![CI](https://github.com/kotoba-lang/org-ietf-rdap/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ietf-rdap/actions/workflows/ci.yml)

**RDAP** (RFC 7480 / 9082 / 9083, status mapping per RFC 8056) **and WHOIS**
(RFC 3912) — the two public read surfaces of a domain registry, rendered from
one source of truth. Portable `.cljc`, no HTTP server, no clock.

[`srs`](https://github.com/kotoba-lang/srs) holds the registry state and
[`org-ietf-epp`](https://github.com/kotoba-lang/org-ietf-epp) is how registrars
change it. This is how everyone else reads it.

## One projection, two renderings

WHOIS lives here rather than in its own repository on purpose. A registry that
computes statuses twice — once for RDAP, once for WHOIS — eventually shows a
domain as locked in one and unlocked in the other, and the registrant sees
whichever they happened to query. Both render from `srs.core/info`, which is
already status-projected and already stripped of the transfer secret, so
neither function *can* publish an `authInfo` even if handed the wrong map.

The one place they deliberately disagree:

| | status spelling |
|---|---|
| RDAP | `client transfer prohibited` — RFC 8056 space-separated lowercase |
| WHOIS | `clientTransferProhibited https://icann.org/epp#clientTransferProhibited` |

Registrar parsers match the camelCase EPP name plus the ICANN URL; RDAP clients
expect the RFC 8056 form. Both are correct for their audience.

## RFC 8056 is specified, and registries invent it anyway

The two vocabularies look similar enough that guessing feels safe. The places
they do not line up are exactly the places a guess is wrong:

- **`ok` becomes `active`.** RDAP has no `ok`. A client checking for it finds
  nothing and concludes the domain has no status at all.
- **The RGP statuses are in scope** (RFC 8056 §4), and they are what
  distinguishes a redeemable name from one past rescue. `srs` carries both
  `pendingDelete` and `redemptionPeriod`, so the projection carries both
  `pending delete` and `redemption period`. Mapping only the EPP core statuses
  drops the distinction that decides whether a registrant can still get their
  name back.
- **An unknown status is dropped, not transliterated.** `camel->rdap` exists
  and `project` deliberately does not call it: emitting an invented value that
  is not in RFC 9083 §10.2 is worse than emitting none.
- **The projection is sorted.** RDAP responses are cached and diffed; an
  unordered set serialized in hash order gives a different body for the same
  state on different hosts.

## Structures that are easy to get wrong quietly

**Dates are events, not members.** There is no `expires` in RDAP. Each date is
an `eventAction` from the IANA registry plus an `eventDate` — and it is
`"expiration"`, not `"expires"`, and `"registration"`, not `"registered"`.

**`rdapConformance` is top-level only** (RFC 9083 §4.1). Repeating it inside an
embedded entity or nameserver is a common bug that makes responses larger and
no more informative. `res/domain` builds the nested form; `res/top-level` adds
the members that belong only at the top.

**A redacted registrant is an entity with no jCard**, not an absent entity.
Post-GDPR most registries publish no registrant contact data; omitting the
entity entirely would tell a client there is *no registrant*.

**jCard is a shape, not a map.** `["vcard", [[name, params, type, value], …]]`,
every property four elements, `version` first and equal to `"4.0"` or parsers
reject the whole entity, and `adr` a **seven**-element array in a fixed order
where position carries the meaning — a five-element array silently relabels the
country as the postal code. `rdap.jcard` builds it so no call site has to.

**An out-of-zone nameserver carries no `ipAddresses` member.** An empty one
asserts it has no addresses rather than that the registry does not know.

## HTTP status is part of the answer

`rdap.service/handle` returns `{:status :headers :body}` with the body as plain
data — a Worker, a Ring handler and a test all call the same function.

- **404 with an RDAP error body** for a name that does not exist. A 200 carrying
  an error object is a response intermediaries cache as success.
- **`errorCode` equals the HTTP status.** Two places to say the same thing means
  two places to disagree.
- **`application/rdap+json`**, not `application/json` (RFC 7480 §4.2).
- **400, not 404, for a malformed name.** "Not a well-formed domain name" and
  "no such domain" are different facts, and a registrar automating against the
  API needs to tell a bug in its client from a name that is free.
- **Search is 501, explicitly.** RFC 9082 §4 makes `/domains?name=…` optional.
  An unbounded search over a registry's whole namespace is a bulk-extraction
  endpoint, and offering one by accident is how registration data leaves a
  registry in bulk. A documented "not implemented" beats a silent 404 that reads
  as "no results".

## Usage

```clojure
(require '[rdap.service :as rdap] '[rdap.whois :as whois] '[json.core :as json])

(def opts {:base "https://rdap.example/rdap"
           :tos-url "https://example/tos"
           :registrar-name "Example Registrar, Inc."})

(rdap/handle registry :get "/domain/example.com" now opts)
;; => {:status 200
;;     :headers {"Content-Type" "application/rdap+json" …}
;;     :body {"objectClassName" "domain" "ldhName" "example.com"
;;            "status" ["active"] "events" [{"eventAction" "registration" …}] …}}

;; the body is data; serialize at the edge
(json/encode (:body r))

;; port 43
(whois/respond query-line #(srs/info registry % now) opts)
```

## Scope

- **In:** domain lookup, `/help`, the RFC 8056 status mapping, jCard entities,
  RDAP error responses with correct HTTP statuses, and the WHOIS text surface.
- **Also served:** `nameserver` lookups, when the caller supplies a
  `:host-lookup` — `srs.host` models hosts now. Without one it is still 501,
  because a deployment that stores nameservers as plain strings has nothing to
  answer with and 404 would be a lie for a name that plainly exists in the zone.
  `linked` reaches RDAP as `associated` through the same RFC 8056 projection as
  every other status, and the *list* of linked domains is never published —
  which domains use a nameserver is not something a public lookup should
  enumerate.
- **Not served:** the `entity` object class, which answers 501 for the same
  reason — `srs` does not model contacts as first-class objects yet.
  Also not implemented: search (deliberately, above), RFC 9224 bootstrap (that
  is IANA's file, not a registry's), and RFC 9537 redaction signalling — this
  library redacts, but does not yet emit the `redacted` member describing what
  it withheld.
- **Not here:** HTTP itself, TLS, rate limiting, and authentication for
  differentiated access. RDAP's whole point over WHOIS is that it can
  authenticate and show more to authorized clients; that policy belongs to the
  deployment.

## Test

```
kbb -M:test
```

33 tests / 98 assertions.
