# kaiyu

**回遊（かいゆう）— how visitors move through a site, measured without
identifying them.** The name is the domain word, not a metaphor: 回遊 is what
the two sites this was extracted from were already calling the thing they
wanted to compare. A portable `.cljc` library, zero dependencies, no host
effects.

It owns the rules a site needs to answer 「どの面が読まれ、次にどこへ行くか」
from counters alone:

| ns | what it owns |
|---|---|
| `kaiyu.core` | dwell buckets, acquisition buckets, route normalization (whitelist), transition edges, report windows, `collected-since` semantics |
| `kaiyu.session` | the browser-side accounting, as a pure reducer: `(step state event) -> [state' emissions]` |
| `kaiyu.diagnose` | what a report SAYS is wrong — ranked findings, each a question a human can answer |

`kaiyu.session` takes exactly one choice from its host, `:on-hide`:

- **`:close`** (default) — a tab-hide closes the view out and emits its dwell;
  returning starts a fresh segment with its own row. **One row = one
  uninterrupted period of attention.**
- **`:pause`** — hiding only stops the clock; one row is emitted when the view
  is finally left. **One row = total attention on that view visit.**

Time never accrues while hidden under either. The default is `:close` because
that is what the existing rows in club-shinshi-app and net-babiniku already
mean — extracting a library is not a licence to redefine data that has already
been collected.

Storage and transport stay with the host — a Worker writing D1 rows, a Pages
Function, a browser sending a beacon. The *vocabulary* does not, because two
sites that pick their own bucket boundaries produce numbers that look
comparable and are not.

## The invariant

**No visitor identifier, ever.** No session id, no cookie of its own, no
fingerprint, no duration in seconds, no path, no query value. Counts, dates,
and names drawn from closed sets that live in this library.

That is a real constraint with a real price, stated here so nobody rediscovers
it as a surprise: paths of three or more hops, per-user funnels, causal
attribution of an exit, and cohort-by-behaviour comparison are **unavailable**.
Buying them means changing what is stored about people. That is a privacy
decision, made in the consuming product's own privacy policy — not something to
reach for by adding a field here.

Concretely, `shinshi.club`'s `legal/privacy.md` §1.2 states publicly that the
service holds "counts and dates only — no IP address, no device fingerprint,
and no user identifier". A library that made widening easy would make that
sentence false.

## Why a whitelist, not a sanitizer

`normalize-route` takes the site's vocabulary as an argument and maps anything
else to `"other"`. A sanitizer lets an unexpected value through in a modified
form, which is exactly how a scene id, a typed search term, or a full path ends
up in a table that promises counts and dates.

Drift is tolerable in one direction only. A route the app added but the
vocabulary does not name reports as `"other"` — coarser, still correct. The
reverse must never happen.

The same asymmetry applies to dwell buckets, and there the correct host
behaviour is **drop, not default**: an unknown bucket is a client bug or a
forgery, and folding it into a default pollutes the very distribution the table
exists to hold.

## Usage

```clojure
(require '[kaiyu.core :as kaiyu] '[kaiyu.session :as session])

(def routes #{"home" "video" "chat" "ranking"})

;; write path (host validates before it stores)
(kaiyu/normalize-route routes "boa-hancock-scene-77")  ;=> "other"
(kaiyu/valid-dwell-bucket? "bogus")                    ;=> false  (drop it)
(kaiyu/transition routes "video" "video")              ;=> nil    (not a navigation)

;; read path
(def win (kaiyu/window "2026-08-07" {:days 7}))
;;=> {:days 7 :from "2026-08-01" :to "2026-08-07"}   ← both ends inclusive
(kaiyu/section win rows "2026-08-06")
;;=> {:rows [...] :collected-since "2026-08-06" :state :partial}

;; browser accounting, without a browser
(session/drive (session/init 0 nil)
               [{:type :navigate :to "home" :now 0 :vocabulary routes}
                {:type :navigate :to "video" :now 12000 :vocabulary routes}
                {:type :end :now 200000}])
;;=> [state [{:t :dwell :route "home" :bucket "10_29"}
;;           {:t :nav :from "home" :to "video"}
;;           {:t :dwell :route "video" :bucket "180_plus"}]]
```

## Judgment is separate, and refuses to run on a doubtful instrument

`kaiyu.diagnose` turns a report into ranked findings (bounce, dead end,
unreached page, single-channel arrival). Two rules make it usable by a loop:

- **Measurement findings short-circuit.** If any section is `:not-measured`
  over a window the site was live for, the site findings are not reported at
  all — not sorted below, not included. Reporting both invites acting on the
  ones that are easier to act on, which are exactly the ones that might be
  artefacts of a broken read.
- **A finding is a question, never a remedy.** The data is counts and dates
  with no visitor identity, so it can locate where attention stops and where it
  never arrives; it cannot say why. `->issue` writes that limitation into the
  issue body.

`top-finding` returns nil when there is nothing to say. A loop must treat that
as a valid round — one that must file an issue every round files noise on the
rounds when the site is fine, and noise is what makes a queue unread.

## `collected-since` is not decoration

An empty section means one of three things, and a report that cannot tell them
apart is not a report:

- `:not-measured` — nothing was ever collected (or collection began after the
  window). The question was never asked.
- `:partial` — collection began inside the window.
- `:measured` — collection covers the window; empty means empty.

This exists because a `collected-since: null` next to a zero reads as
「誰も来ていない」 when it usually means 「まだ測っていない」 — and, on
2026-08-07, once meant 「読めていない」: `/_metrics/audience` had been answering
200 with zeros for a day while the underlying table held 595 pageviews, because
every read threw and was swallowed (ADR-2608060900).

## Origin

Extracted 2026-08-07 from two independent implementations that had converged on
the same shape a day earlier:

- `network-awai/club-shinshi-app` — `shinshi.worker.telemetry` (Worker + D1)
- `network-awai/net-babiniku` — `babiniku.analytics` + `functions/api/track.js`
  (browser + Pages Function)

Both had already duplicated the bucket boundaries, the whitelist rule, and the
window arithmetic. The third consumer is what made the duplication worth
removing rather than worth watching — `com-junkawasaki/root` ADR-2608060900
said to wait for exactly that.

Their shipped vocabularies are checked into `test/kaiyu/core_test.cljk` as
fixtures, so a change here that would alter either site's numbers fails loudly
instead of being discovered when two products stop being comparable.

## Not this library

- **`kotoba-lang/log`** — trace/span structured logging. Observability, not
  product analytics.
- **`kotoba-lang/senden`** — campaigns, marketing funnel, attribution, on
  `chobo.ledger`. Answers 「どこに払ったか」; kaiyu answers 「入ったあと
  どう動いたか」. `kaiyu/acquisition-source` is the seam between them, and it
  deliberately carries a bucket NAME, never a campaign id.
- **Heatmaps / session replay.** A non-goal, not a gap. Coordinate streams are
  a different privacy class and cannot be added without changing the
  consuming product's privacy policy first (ADR-2608060900 D3).

## Tests

```bash
kbb --backend sci --classpath src:test test/run_tests.cljs.cljk   # 31 tests / 140 assertions
kbb -M:test                                    # same suite on the JVM
```
