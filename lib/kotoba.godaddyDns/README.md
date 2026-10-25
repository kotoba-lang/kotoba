# godaddy-dns-clj

GoDaddy DNS management agent in **portable Clojure** — every namespace is
`.cljc`, designed for **Clojure-on-WASM hosts** (SCI, ClojureScript,
GraalVM, kotoba-clj) as well as the JVM. The DNS API itself is an
**injected host capability** (`IDns`); writes are **dry-run by default**
and every action is persisted through a **Datomic API** as an audit trail.

Built on [langgraph-clj](https://github.com/com-junkawasaki/langgraph-clj)
/ [langchain-clj](https://github.com/com-junkawasaki/langchain-clj).
Sibling of [computer-use-clj](https://github.com/com-junkawasaki/computer-use-clj)
and [browser-use-clj](https://github.com/com-junkawasaki/browser-use-clj).

```
src/godaddydns/
  dns.cljc      IDns protocol (host capability) + mock-dns (in-memory zone)
  godaddy.cljc  real GoDaddy Domains API impl over an injected http-fn/json
  tool.cljc     DNS tool vocabulary (list/upsert/delete) + dry-run dispatch
  agent.cljc    sampling loop (langgraph StateGraph) + action log as datoms
```

## Design

- **DNS = injected host capability** — implement `IDns`
  (`-list-domains` / `-list-records` / `-upsert-records!` /
  `-delete-records!`). The real impl (`godaddydns.godaddy`) talks to
  `api.godaddy.com` over an injected `:http-fn` + `:json-read`/`:json-write`
  (zero third-party deps); the bundled `mock-dns` is a deterministic
  in-memory zone so tests and demos run with **no network and no API key**.
- **GoDaddy semantics, faithfully** — `PUT /v1/domains/{domain}/records/{type}/{name}`
  *replaces* the whole record set for a `(type, name)` pair, so
  `-upsert-records!` does exactly that — the mock and the real host agree.
  Auth is the `sso-key {KEY}:{SECRET}` header; point `:base` at
  `https://api.ote-godaddy.com` for the OTE test environment.
- **Dry-run by default** — DNS is destructive, so write tools
  (`upsert_record` / `delete_record`) **plan** instead of mutating: they
  append the intended change to a plan and return `PLANNED: …`. Pass
  `:dry-run false` to commit (`APPLIED: …`). Read tools always run.
- **Audit trail as datoms** — with a `:history-conn` every tool call
  becomes a datom (`:dnsaction/tool`, `:dnsaction/domain`,
  `:dnsaction/applied?`, …): "every record changed in session s1", "all
  sessions that touched example.com" is a Datalog query. Graph
  checkpoints (resume / human-in-the-loop) come from langgraph-clj.

## Quickstart

```clojure
(require '[godaddydns.dns :as dns]
         '[godaddydns.godaddy :as godaddy]
         '[godaddydns.agent :as agent]
         '[langchain.db :as db])

;; host capability: real GoDaddy, or the mock zone:
(def gd (godaddy/godaddy-dns
         {:http-fn host-fetch :json-read … :json-write …
          :key (System/getenv "GODADDY_KEY")
          :secret (System/getenv "GODADDY_SECRET")
          :base godaddy/ote-base}))           ; OTE test env

(def conn (db/create-conn agent/log-schema))

(agent/run
 {:model (model/anthropic-model {:api-key … :http-fn host-fetch …})
  :dns gd
  :task "Point the apex A record of example.com at 5.6.7.8"
  :dry-run true                                ; plan only (default)
  :history-conn conn
  :session-id "s1"})
;; => {:result "…" :done true :applied? false
;;     :plan [{:op :upsert :domain "example.com" :type "A" :name "@" :data "5.6.7.8" :ttl 600}]
;;     :messages […] :steps n}

;; the audit trail is datoms:
(db/q '[:find ?step ?tool ?applied
        :where [?e :dnsaction/step ?step]
               [?e :dnsaction/tool ?tool]
               [?e :dnsaction/applied? ?applied]]
      (db/db conn))
```

Extra tools sit alongside the DNS tools: `(agent/run {:tools [my-tool] …})`.

## Terminal usage

`examples/dns_agent.cljk` is a ready-to-run CLI. With no GoDaddy
credentials it falls back to an in-memory mock zone, so you can try the
whole loop offline:

```sh
# plan only (safe default), mock zone, local Ollama model:
kbb -M:examples -m dns-agent "list records for example.com"

# plan against the real account (OTE test env):
GODADDY_KEY=… GODADDY_SECRET=… GODADDY_BASE=https://api.ote-godaddy.com \
  kbb -M:examples -m dns-agent "set the apex A record of example.com to 5.6.7.8"

# actually apply, with Claude driving:
DRY_RUN=false LLM=anthropic ANTHROPIC_API_KEY=… GODADDY_KEY=… GODADDY_SECRET=… \
  kbb -M:examples -m dns-agent "set the apex A record of example.com to 5.6.7.8"
```

Env: `GODADDY_KEY` / `GODADDY_SECRET` (unset → mock zone), `GODADDY_BASE`
(default production; OTE = `https://api.ote-godaddy.com`), `DRY_RUN`
(default `true`), `LLM` = `ollama` (default) | `gemini` | `anthropic`.
`examples/jvm_host.cljk` provides the JVM host capabilities (a
`java.net.http` `:http-fn`, `clojure.data.json`, and the model switch).

> **Note on GoDaddy write access:** GoDaddy gates the records write API on
> account standing (e.g. a minimum number of domains). The dry-run +
> mock-zone defaults let you develop and demo with no key and no write
> permission; verify your account's API access at
> [developer.godaddy.com](https://developer.godaddy.com/) before using
> `DRY_RUN=false` against production.

## GoDaddy API mapping

| GoDaddy Domains API | godaddy-dns-clj |
|---|---|
| `GET /v1/domains` | `-list-domains` / `list_domains` tool |
| `GET /v1/domains/{d}/records[/{type}[/{name}]]` | `-list-records` / `list_records` tool |
| `PUT /v1/domains/{d}/records/{type}/{name}` (replace set) | `-upsert-records!` / `upsert_record` tool |
| `DELETE /v1/domains/{d}/records/{type}/{name}` | `-delete-records!` / `delete_record` tool |
| `Authorization: sso-key KEY:SECRET` | `godaddy/godaddy-dns` `:key` / `:secret` |
| prod `api.godaddy.com` · OTE `api.ote-godaddy.com` | `godaddy/prod-base` · `godaddy/ote-base` |

See [docs/adr/0001-architecture.md](docs/adr/0001-architecture.md).

## Tests

```sh
kbb -M:test          # mock-only, no network, no key
```

Workspace development against local checkouts (`../langgraph`,
`../langchain`): `kbb -M:dev:test`.

## License

MIT © 2026 Jun Kawasaki
