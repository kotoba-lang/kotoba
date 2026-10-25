# com-google-calendar

**Google Calendar as a connector** — calendars, events and free/busy, with each
tool declaring the OAuth scope it needs so a deployment asks for what it turned
on and nothing more.

Portable `.cljc`. One dependency, [`kotoba-lang/connector`](https://github.com/kotoba-lang/connector),
which carries the descriptor model, the OAuth flow and the invoke path. This
repository carries the two things specific to Calendar: how a tool call becomes
a request, and how a response becomes a result.

## Tools

| tool | effect | scope |
|---|---|---|
| `google_calendar_list_calendars` | read | `calendar.readonly` |
| `google_calendar_list_events` | read | `calendar.readonly` |
| `google_calendar_get_event` | read | `calendar.readonly` |
| `google_calendar_freebusy` | read | `calendar.readonly` |
| `google_calendar_create_event` | **write** | `calendar.events` |

`connector.model/read-only` drops the last row, and the `calendar.events` scope
goes with it — no separate list to keep in step.

## Why free/busy is here

ADR-2608093000 records that `cloud-itonami-app`'s `tenant_connection`
capability vocabulary is entirely inward-facing — `tenant.read`,
`workspace.write`, `actor.invoke`, `repository.*` — with nothing meaning "this
app may read the owner's free time". `google_calendar_freebusy` is that missing
outward capability, in a plane where it can be granted and revoked. It returns
times only: no titles, no attendees, no descriptions.

## Two things that are easy to get wrong

**`singleEvents=true&orderBy=startTime`** on `list_events`. Without it a weekly
stand-up comes back as one row with a recurrence rule, and every caller has to
expand it. With it, "events this week" means occurrences.

**A calendar id is an email address.** `jun@example.com` unencoded in a path
addresses a different resource. `connector.uri/encode` is used for every path
segment; there is a test for exactly this.

## Usage

```clojure
(require '[connector.registry :as reg]
         '[connector.invoke :as invoke]
         '[google-calendar.connector :as calendar])

(def registry (reg/registry [calendar/provider]))

(invoke/call registry "google_calendar_freebusy"
             {"timeMin" "2026-08-08T00:00:00Z"
              "timeMax" "2026-08-15T00:00:00Z"
              "calendarIds" ["primary"]}
             {:http my-http :tokens my-tokens})
;; => {:busy {"primary" [{:start "…" :end "…"}]} :errors {}}
```

This namespace cannot obtain a credential. `request` receives a tool name and
arguments; `connector.invoke` attaches the Authorization header.

## Declaration

`connector.edn` states the contract in a form readable without loading Clojure
(the role `capability.edn` plays for the `capability-` family). It is
**generated**, and the test suite fails if the committed file has drifted:

```sh
kbb --backend sci --classpath "src:../connector/src" emit-connector-edn.cljk
```

## Tests

```sh
kbb --backend sci --classpath "src:test:../connector/src" run-tests.cljk   # 12 tests, 43 assertions
kbb -M:test
```

No network, no fixtures server: a request is a map, so the assertions are value
comparisons.

## Naming

`google.com` reverses to `com-google`; the subject is `calendar`. The origin
plane rule is `manifest/repository-rules.edn` `:vocabulary/id :origin`
(ADR-2608040100) and `connector.validate/name-conformant?` checks it.
