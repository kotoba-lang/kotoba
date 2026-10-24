# ical-clj (カレンダー予定)

[![CI](https://github.com/kotoba-lang/ical/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/ical/actions/workflows/ci.yml)

Handle **iCalendar (RFC 5545) as EDN/Clojure data** in portable Clojure — every
namespace is `.cljc`, with **zero third-party runtime deps**, so it runs on the JVM,
ClojureScript, and Clojure-on-WASM hosts (SCI). A calendar is plain data you can
`assoc`, `diff`, store in Datomic, or generate; the library adds structural
validation, iCal text I/O, and pure recurrence (RRULE) expansion around it.

Sibling of the other reusable `*-clj` kernels in this org
([koe-clj](https://github.com/com-junkawasaki/koe-clj),
[bpmn-clj](https://github.com/com-junkawasaki/bpmn-clj),
[dmn-clj](https://github.com/com-junkawasaki/dmn-clj)). Synergy with
[yotei](https://github.com/com-junkawasaki/koe-clj) (予約) booking and
koe-clj voice-reception: a booking flow produces EDN; ical-clj serialises it to
`.ics` for CalDAV export or emits occurrences for reminder scheduling.

## Why a shared library (org placement)

Per the three-org rule, the **reusable** calendar model lives in **com-junkawasaki**;
**public-benefit actor instances** (e.g. an appointment scheduler for a clinic) live
in **etzhayyim**; any **business/private deployment** lives in **gftdcojp**. ical-clj
carries no domain schedule and no engine bindings — those are host-injected or
assembled in a consuming actor.

## The model: iCalendar as EDN (`ical.model`)

A calendar is a map keyed by namespaced `:ical/*` keys; events and todos are plain
vectors for ordered iteration:

```clojure
{:ical/prodid  "-//com-junkawasaki//ical-clj//EN"
 :ical/version "2.0"
 :ical/events
 [{:ical/uid     "weekly-standup@host"
   :ical/summary "Weekly Standup"
   :ical/dtstart {:y 2026 :m 7 :d 1 :hh 10 :mm 0}
   :ical/dtend   {:y 2026 :m 7 :d 1 :hh 11 :mm 0}
   :ical/rrule   {:ical/freq     :weekly
                  :ical/interval 1
                  :ical/count    5
                  :ical/byday    [:mo :we]}}]
 :ical/todos [...]}
```

Date-time values are plain maps `{:y :m :d :hh :mm}`. **No java.time / Date** —
all arithmetic is pure (see `ical.execute`).

A threading-friendly builder:

```clojure
(require '[ical.model :as m])

(def cal
  (-> (m/calendar {:prodid "-//acme//en" :version "2.0"})
      (m/add-event
       (m/event "standup-001@acme"
                {:summary "Weekly Standup"
                 :dtstart (m/dt 2026 7 1 10 0)
                 :dtend   (m/dt 2026 7 1 11 0)
                 :rrule   (m/rrule {:freq :weekly :interval 1
                                    :count 10 :byday [:mo :we]})}))))
```

## Validation (`ical.validate`)

`problems` returns a vector of `{:ical/severity :ical/code :ical/id :ical/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[ical.validate :as v])
(v/valid? cal)            ;=> true
(v/problems broken-cal)   ;=> [{:ical/severity :error :ical/code :vevent/missing-uid …}]
```

Errors: VEVENT missing `:ical/uid` or `:ical/dtstart`; RRULE with unknown `:ical/freq`;
RRULE with both `:ical/count` and `:ical/until`; unknown BYDAY weekday token.

## iCalendar I/O (`ical.ical`)

```clojure
(require '[ical.ical :as ical])

(ical/parse-str (slurp "meeting.ics"))  ; RFC 5545 text → EDN model
(ical/emit-str cal)                     ; EDN model → RFC 5545 text (round-trips)
```

`parse-str` handles RFC 5545 line unfolding, property parameters, value unescaping
(`\\`, `\;`, `\,`, `\n`), DTSTART/DTEND (`YYYYMMDD[Thhmmss[Z]]`), and full RRULE
parsing. A sample calendar is bundled at `resources/ical/sample.ics`.

## Recurrence expansion (`ical.execute`)

```clojure
(require '[ical.execute :as ex])

(ex/occurrences event
                {:y 2026 :m 7 :d 1 :hh 0 :mm 0}   ; from (inclusive)
                {:y 2026 :m 12 :d 31 :hh 0 :mm 0}) ; to   (exclusive)
;=> [{:y 2026 :m 7 :d 1 :hh 10 :mm 0}
;    {:y 2026 :m 7 :d 6 :hh 10 :mm 0}  …]
```

`occurrences` expands the `:ical/rrule` and returns a vector of
`{:y :m :d :hh :mm}` maps (preserving the original `:hh/:mm`) in `[from, to)`.
Supports:

- **FREQ**: `:daily` / `:weekly` / `:monthly` / `:yearly`
- **INTERVAL**: step multiplier (default 1)
- **COUNT**: exact occurrence count
- **UNTIL**: inclusive end date
- **BYDAY** (weekly): emit matching weekdays within each interval-th week
  (e.g. `BYDAY=MO,WE` yields both Monday and Wednesday per week)

All calendar arithmetic is pure, using the Howard Hinnant proleptic-Gregorian
day-number algorithm (`days_from_civil` / `civil_from_days` / `weekday_from_days`)
— no `java.time`, no `js/Date`, no external dep.

## Test

```
kbb -M:test
```
