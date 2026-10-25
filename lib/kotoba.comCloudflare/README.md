# com-cloudflare

Portable (`.cljc`) Cloudflare API v4 client -- REST + GraphQL Analytics +
Logpush job management. One tested auth/HTTP boundary, injectable transport,
for any kotoba-lang/gftdcojp project that needs to read Cloudflare zone,
Worker, Pages, or analytics state instead of re-deriving `curl`/HTTP-call
boilerplate ad hoc.

## Why this exists

`gftdcojp/cloud-itonami` built `cloud-itonami.analytics` (ADR-0010) as an
itonami-specific, one-off GraphQL Analytics client while investigating its
own portfolio's real traffic. That work also hand-rolled several ad hoc
`curl` calls (DNS records, Workers Custom Domains, Pages projects) to
answer one real question: *what actually serves this hostname?* --
`app.itonami.cloud` turned out to be bound to a different Worker's Custom
Domain, not visible from DNS or Pages alone (ADR-0010, 2026-07-04). Every
one of those was a real, useful capability that had no home to live in for
reuse by the next project that needs the same thing. This library is that
home.

## Design

```text
cloudflare.client      -- auth (CLOUDFLARE_API_TOKEN) + HTTP (injectable :http-fn) + GraphQL/REST envelopes
cloudflare.analytics   -- GraphQL Analytics: daily traffic trend, per-path/device/country/status breakdown
cloudflare.zones       -- zone list, DNS records (read)
cloudflare.workers     -- zone-scoped routes, account-scoped Custom Domains, worker scripts (read)
cloudflare.pages       -- Pages projects + their bound domains (read)
cloudflare.logpush     -- Logpush job management (list/create/delete) -- NOT log fetching/parsing, see below
cloudflare.stream      -- Stream Live: live inputs (WHIP/RTMPS/SRT ingest) + RTMP live outputs (YouTube/Twitch fan-out)
```

Query/request construction and response parsing are pure `.cljc`. The
actual HTTP call is JVM-only by default (`java.net.http`) but every
function takes an injectable `:http-fn` (`{:url :method :headers :body} ->
{:status :body}`, the same convention `cloud-itonami.runtime`/
`cloud-itonami.mail` already use) -- every namespace here is tested with a
stub, never only against a live account.

## Usage

```clojure
(require '[cloudflare.analytics :as analytics])

;; CLOUDFLARE_API_TOKEN in the environment, or pass :token explicitly
(analytics/daily-report! {:zone-tag "..." :since (analytics/iso-date 7) :until (analytics/iso-date 0)})
;; => {:ok? true :days [...] :totals {:requests ... :page-views ... :uniques ... :bytes ...}}

(analytics/path-report! {:zone-tag "..." :since (analytics/iso-instant-hours-ago 23) :until (analytics/iso-instant-hours-ago 0)})
;; => {:ok? true :total ... :by-path {...} :by-device {...} :by-country {...} :by-status {...}}
;; host omitted = whole zone. A host-filtered call can legitimately return
;; zero rows if that host has no traffic while the zone does -- that's a
;; real finding, not a bug (see ADR-0010's app.itonami.cloud discovery).

(require '[cloudflare.workers :as workers])
(workers/custom-domains account-id)
;; => [{:hostname "app.itonami.cloud" :service "local-murakumo" ...} ...]
;; -- the answer to "what actually serves this hostname" when DNS/Pages don't have it.
```

### Stream Live — reaching YouTube Live / Twitch from a browser

A browser cannot speak RTMP, so it cannot publish to YouTube Live or Twitch
directly. A Cloudflare Stream **live input** accepts WHIP/WebRTC from the
browser; **live outputs** attached to it make Cloudflare re-broadcast the
same stream onward over RTMP. Pair this with
[`kotoba-lang/webrtc`](https://github.com/kotoba-lang/webrtc)'s
`kotoba.webrtc.whip` on the browser side.

```clojure
(require '[cloudflare.stream :as stream])

(def input (stream/create-live-input! account-id {:name "babiniku-stage"}))
;; => {:uid "..." :whip-url "https://customer-….cloudflarestream.com/…/webRTC/publish"
;;     :whep-url ... :rtmps-url ... :rtmps-stream-key ... :raw {...}}

(stream/create-live-output! account-id (:uid input)
                            {:platform :youtube :stream-key key})   ; :twitch, or :url for anything else

(println (stream/live-input-summary input))   ; credential-free, safe to log
```

`recording` defaults to `"off"`: recording turns every broadcast into
stored minutes that keep billing after the stream ends.

`validate-output` runs before any output is posted and rejects the ways a
destination silently never connects — a non-RTMP scheme, a stream key with
a pasted-in trailing newline (the RTMP handshake carries it verbatim), or
the key already appended to the ingest URL. Stream keys are broadcast
credentials, so nothing here ever renders one whole: `redact-key` shows
four characters and a length, and `live-input-summary` redacts even the
RTMPS key Cloudflare returns.

Every `*-request` builder is pure `.cljc` returning `{:method :path :url
:body}`, so ClojureScript and `nbb` callers — the provisioning script that
already has the stream key in hand, for instance — can use them without a
JVM; the `*!` fns are the JVM convenience layer over `client/rest!`.

## Logpush scope (honestly stated)

`cloudflare.logpush` manages Logpush *jobs* -- it does not fetch or parse
the log lines a job streams to its destination (R2/S3/GCS/Azure/Splunk/
...). Reading/parsing that stream is destination-specific and deliberately
out of scope here; build that in its own namespace once a real project has
picked a real destination, rather than speculatively ahead of one.

GraphQL Analytics only has aggregates (counts by dimension) -- it cannot
explain what a *specific* request's response, exception, or trace looked
like. `gftdcojp/cloud-itonami` hit exactly this wall investigating
unexplained edge-status-499s on one path
([net-kotobase#153](https://github.com/gftdcojp/net-kotobase/issues/153),
2026-07-04): aggregates confirmed the 499s were real but couldn't explain
why. A Logpush job on `http_requests` or `workers_trace_events`, wired to
a real destination, is the concrete next step for that kind of
investigation -- this namespace is the job-management half of getting
there.

## Test

Two suites, and **both are required** -- see ADR 0019.

```sh
kbb -M:test                                  # JVM
kbb --backend sci test/cloudflare/oracle_cljs_gate.cljk        # ClojureScript (from repo root)
```

Stubbed `:http-fn` throughout -- no `CLOUDFLARE_API_TOKEN` or live account
needed to run either.

The public API delegates its pure decisions to precompiled Kotoba KIR
(`resources/cloudflare/oracle/*.kir.edn`), and the runtime that matters here is
JavaScript. **A green JVM run is not evidence about ClojureScript**: until
2026-08-12 the shipped artifacts threw `string substring indexes are out of
bounds` on nbb for 40+ exports -- the whole deploy-validation path among them --
while `kbb -M:test` stayed green, because the kir interpreter's bounds guard
rejected the `js/BigInt` that a cljs `:i64` is.

The cljs gate executes 220 cases covering **every export of every shipped
artifact** through `cloudflare.kotoba.oracle/call` and fails on a raised
exception, on a result that differs from the JVM, or on any export that has no
case at all. The case table is shared with the JVM suite
(`cloudflare.oracle-cases-test`), so the two runtimes cannot silently diverge.

To change the table, edit the arguments in `test/cloudflare/oracle_cases_gen.cljk`
and regenerate:

```sh
kbb -M:oracle-cases-gen
```

Expectations are derived by running the cases on the JVM, so read the diff --
a changed expectation is a changed decision.
