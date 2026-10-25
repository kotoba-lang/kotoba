# calendar

[![CI](https://github.com/kotoba-lang/calendar/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/calendar/actions/workflows/ci.yml)

Portable CLJC model for kotoba-lang/calendar.

The bounded Kotoba profile lives in `src/calendar/model.kotoba` and
`src/calendar/validate.kotoba`. It represents at most 8 nominal events with
keyword IDs and signed-i64 time coordinates. Updates are persistent, event
duration must be positive, and the closed graph requires no host capability.
The open-schema CLJC model remains authoritative for ISO time strings, titles,
attendees, and resource links; those domains are not silently narrowed.

## Which rules run from the shipped Kotoba cores

Both time rules are decided by Kotoba and executed from the shipped
artifacts through `calendar.kotoba-oracle`. A missing artifact throws rather
than falling back.

| rule | core | host | what the host still does |
|---|---|---|---|
| do two events share an instant | `model.kotoba/overlaps?` | `model.cljc/overlaps?` | reads two maps, refuses an absent instant (`:i64` has no absence), ranks four instants into the guest's domain |
| does an event occupy any time | `validate.kotoba/event-valid?` | `validate.cljc/occupies-time?` | reads two keys, ranks two instants |

Neither host computes its rule. Everything phrased in terms of them —
`conflicts`, `free?`, `event-problems`, `problems`, `valid?` — follows.

What is **not** delegated, and why, is `kotoba-oracle/host-answered`: the
remaining exports hold the calendar's events map inside the guest, and that
map grows with the calendar. Measured at the pinned interpreter, a calendar
crosses the entry boundary at twelve events and is refused at **thirteen**
(`ADT value exceeds node limit`). `validate.kotoba/valid?` additionally
answers `false` for any calendar over eight events by construction, while
`validate.cljc/valid?` reports on every event of an open-schema one. Those
exports keep their parity and conformance gates; that is what those cores
are for, not a step that has not been taken.

## The ClojureScript boundary is not the JVM one

```bash
kbb --backend sci scripts/cljs-boundary-check.cljk
```

A `:i64` field inside a record must be a `js/BigInt` on ClojureScript; a
`js/Number` is rejected. On the JVM the two are the same value, so
`kbb -M:test` cannot see the difference and a host that forgot the
conversion stays green there. It happened: `overlaps?` threw
`value is not a signed i64` on every ClojureScript call for a day. The seam
converts (`kotoba-oracle/i64`) and the script above is what fails if it
stops.

`kotoba-lang/kotoba-kir` is therefore a runtime dependency, pinned to the kir
the pinned compiler emits for — a test asserts the two pins are the pair the
compiler itself declares. The compiler stays test-only.

```bash
kbb -M:test:gen   # regenerate resources/calendar/oracle/*.kir.edn
```

Pages editor: https://kotoba-lang.github.io/calendar/

The Pages UI is local to kotoba-lang and does not redirect to external hosts.

## Test

```bash
kbb -M:test
```
