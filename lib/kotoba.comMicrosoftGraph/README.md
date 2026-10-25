# com-microsoft-graph

**Microsoft 365 as a connector**, through Microsoft Graph — mail and calendar
on one grant.

Portable `.cljc`. One dependency, [`kotoba-lang/connector`](https://github.com/kotoba-lang/connector).

## Tools

| tool | effect | scope |
|---|---|---|
| `microsoft_graph_get_profile` | read | `User.Read` |
| `microsoft_graph_list_messages` | read | `Mail.Read` |
| `microsoft_graph_get_message` | read | `Mail.Read` |
| `microsoft_graph_send_mail` | **write** | `Mail.Send` |
| `microsoft_graph_list_events` | read | `Calendars.Read` |
| `microsoft_graph_get_schedule` | read | `Calendars.Read` |

## Named for the API, not the product

Graph is one API over many services, so `Mail.Read` and `Calendars.Read` are
two scopes on one client rather than two connectors. That is the opposite of
the Google decision in this fleet, where Drive, Gmail and Calendar are three
APIs under one OAuth client and therefore three connectors that
`connector.consent` groups back into a single grant. Both shapes end at the
same place: one consent dialog per OAuth client, asking for exactly the enabled
tools' scopes.

## Three Graph behaviours encoded here

**`offline_access` is in the base scopes.** Without it Microsoft issues no
refresh token, and a connector needing a manual reauthorization every hour is
one nobody leaves enabled.

**`$search` and `$orderby` cannot be combined** — Graph answers `400` for a
reason the caller cannot see. The ordering is dropped when a search is asked
for; a search result is already relevance-ranked.

**A time window selects `calendarView`.** `/me/events` returns the series
master for a recurring meeting; `/me/calendarView` expands occurrences. With
`startDateTime`/`endDateTime` given, occurrences are what "events this week"
means.

`microsoft_graph_send_mail` defaults `saveToSentItems` to `true`: a message the
sender cannot find in Sent Items afterwards is one they cannot prove they sent.
An explicit `false` is honoured.

## Usage

```clojure
(require '[connector.registry :as reg]
         '[connector.invoke :as invoke]
         '[microsoft-graph.connector :as graph])

(def registry (reg/registry [graph/provider]))

(invoke/call registry "microsoft_graph_get_schedule"
             {"schedules" ["jun@example.com"]
              "startTime" "2026-08-08T00:00:00"
              "endTime"   "2026-08-08T23:59:59"}
             {:http my-http :tokens my-tokens})
```

This namespace cannot obtain a credential; `connector.invoke` attaches it.

## Declaration

`connector.edn` is generated; the test suite fails if it has drifted.

```sh
kbb --backend sci --classpath "src:../connector/src" emit-connector-edn.cljk
```

## Tests

```sh
kbb --backend sci --classpath "src:test:../connector/src" run-tests.cljk   # 12 tests, 44 assertions
kbb -M:test
```

## Naming

`microsoft.com` → `com-microsoft`, subject `graph`. `graph.microsoft.com` is a
host under the same registrable domain, so the recorded fact is
`microsoft.com` (ADR-2608040100).
