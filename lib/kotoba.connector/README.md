# connector

**This repository is the contract for connecting this workspace to an external
service** — the kernel behind repositories like `com-google-calendar`, in the
sense Claude and Codex use the word "connector": a named integration with a
declared auth flow, a declared tool surface, and a consent screen that can say
in words what it is asking for.

Portable `.cljc` (JVM, ClojureScript, nbb, SCI). One dependency
(`kotoba-lang/org-anthropic-mcp`, and only `connector.mcp` uses it). No I/O:
every function returns a URL, a request map or a result, and the host performs
the request.

## Why it exists

Measured 2026-08-08, this workspace had every part of a connector and no
connector:

| in place | missing |
|---|---|
| an MCP **server** with OAuth 2.1, RFC 9728 discovery and scopes (`cloud-itonami-app`) | any way to register an external service |
| OAuth to Google / Microsoft / GitHub, hard-coded in one 2,174-line namespace | a second deployment being able to add a third provider without editing that file |
| `tenant_connection` capability leases (request → approve → TTL → revoke) | any capability pointing *outward* |
| 1,215-entry app catalog | an "install" |

So it could be connected **to**, and had three providers it could reach, and no
plane in which "a connector" was a thing you could hold. `agent-control`'s tool
list is a `cond->` over four hard-coded vectors; adding an integration meant
editing the application. ADR-2608093000 names the same gap from the app side.

## The model

A **descriptor** is data — printable, diffable, storable, safe in a catalog:

```clojure
(-> (m/connector "com.google.calendar" "Google Calendar"
                 {:origin-domain "google.com"
                  :base-url "https://www.googleapis.com"
                  :auth (m/oauth2 {:authorization-endpoint "https://accounts.google.com/o/oauth2/v2/auth"
                                   :token-endpoint         "https://oauth2.googleapis.com/token"
                                   :client-id-env          "GOOGLE_CLIENT_ID"
                                   :pkce?                  true})})
    (m/add-tool "google_calendar_freebusy"
                {:description  "Free/busy windows for one or more calendars"
                 :effect       :read
                 :scopes       ["https://www.googleapis.com/auth/calendar.readonly"]
                 :input-schema {:type "object" ...}}))
```

A **provider** pairs that descriptor with the two things that cannot live
inside data — `request` (tool call → HTTP request map) and `normalize`
(response → result). That pair is a connector repository's entire public
surface.

Three properties are worth stating, because each was a choice:

**Scopes are declared per tool.** A deployment running only a calendar reader
asks for `calendar.readonly` and nothing else, even though the same OAuth
client is capable of `gmail.send`. `connector.consent` computes the grant from
what is *enabled*, not from what the connector could do.

**One grant per OAuth client, not per connector.** Drive, Gmail and Calendar
are three connectors sharing one Google client. Asking somebody to approve
Google three times is worse than useless — the second dialog teaches people to
click through. They are grouped by `(authorization endpoint, token endpoint,
client-id env)` and asked once. Grouping by *client* rather than by provider
name is deliberate: two deployments under different OAuth clients must not
share a grant, and nothing here can tell them apart by name.

**A connector never sees the credential.** `request` is handed a tool name and
arguments — never a token, a keychain, an environment, or a way to reach one.
`connector.invoke` attaches the Authorization header. So reviewing a connector
repository does not include checking whether it leaked a credential: it has no
way to obtain one.

## Namespaces

| | |
|---|---|
| `connector.model` | descriptor as EDN, builder, per-tool scope arithmetic, `read-only` |
| `connector.validate` | structural problems; also the origin-plane name check |
| `connector.auth` | OAuth 2.0 authorization-code + PKCE, as URLs and request maps |
| `connector.provider` | descriptor + `request`/`normalize`, validated at load time |
| `connector.registry` | many connectors as one surface; `select` narrows to what is enabled |
| `connector.consent` | grants grouped by OAuth client; `grant-summary` for the screen |
| `connector.invoke` | build → authorize → send → normalize |
| `connector.ports` | `IHttp`, `ITokens` — host-injected |
| `connector.mcp` | projection onto an `mcp.model` manifest + an `mcp.ports/ITool` |

## Usage

```clojure
(require '[connector.registry :as reg]
         '[connector.consent :as consent]
         '[connector.invoke :as invoke]
         '[connector.ports :as ports]
         '[google.calendar.connector :as calendar]
         '[google.gmail.connector :as gmail])

(def registry (reg/registry [calendar/provider gmail/provider]))

;; what an operator turned on
(def enabled (reg/select registry #{"com.google.calendar"} #{"google_calendar_freebusy"}))

;; one consent URL per OAuth client, for exactly those scopes
(consent/authorization enabled {:client-ids  {"GOOGLE_CLIENT_ID" client-id}
                                :redirect-uri "https://app.example/oauth/callback"
                                :state-fn          mint-state!
                                :code-challenge-fn mint-challenge!})

;; run a tool
(invoke/call enabled "google_calendar_freebusy" {"timeMin" "…" "timeMax" "…"}
             {:http   (ports/http-fn my-http)
              :tokens (ports/token-fn my-token-store)})
```

## Testing a connector without a network

`connector.invoke/request-for` returns the request a tool call *would* send,
without the credential. That is the assertion a connector repository's tests
are made of — a request map is a value, so there is no fake server, no
cassette and no recorded traffic:

```clojure
(is (= {:connector.http/method :get
        :connector.http/url    "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        :connector.http/query  {"timeMin" "2026-08-08T00:00:00Z"}}
       (invoke/request-for registry "google_calendar_list_events"
                           {"calendarId" "primary" "timeMin" "2026-08-08T00:00:00Z"})))
```

## Tests

```sh
kbb --backend sci --classpath "src:test:../org-anthropic-mcp/src" run-tests.cljk   # 22 tests, 59 assertions
kbb -M:test
```

## Naming

One connector, one repository, in the **origin plane**: the repository name is
the reverse-DNS of the authority's registrable domain plus the subject
(`google.com` → `com-google` → `com-google-calendar`). The rule is
`manifest/repository-rules.edn` `:vocabulary/id :origin`, the data is
`manifest/origin-domains.edn`, and `connector.validate/name-conformant?`
checks it. Absence of a recorded domain returns `nil`, not `false` —
unverified is not a pass.

Where the origin-plane repository for a service **already exists**, the
connector belongs in it rather than in a new one: two repositories for one
subject in one plane is not allowed (ADR-2608040100). `kotoba-lang/com-github`
already owns GitHub and already has an HTTP-injected client (`github.workflow`),
so the GitHub connector is defined there.

## Related

- `kotoba-lang/org-anthropic-mcp` — MCP manifests as EDN; this library projects onto it
- `cloud-itonami/cloud-itonami-app` — the MCP **server** side (`/mcp`, OAuth 2.1, RFC 9728)
- ADR-2608093000 — app descriptors and the connection protocol
- ADR-2608040100 — the origin plane is reverse-DNS of the real domain
