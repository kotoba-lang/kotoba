# browser-agent-clj

genspark-style **general super-agent** in portable Clojure — one
instruction is planned, delegated across a fleet of specialized
sub-agents (a **Mixture-of-Agents** supervisor), executed against the
agent's **own browser**, and the entire run is persisted as **datoms**
you can query and time-travel.

Every namespace is `.cljc`, designed for **Clojure-on-WASM hosts**
(SCI, ClojureScript, GraalVM, kotoba-clj) as well as the JVM. All I/O —
models, the browser, search/fetch/exec/render, the live transport — is
an **injected host capability**; all state goes through a **Datomic
API**.

Built on the same layering as upstream genspark-over-LLMs:

```
browser-agent-clj            ← this repo: supervisor / planner / fleet / owned browser
  ├─ browser-use-clj         web sub-agent (IBrowser + indexed elements)
  ├─ langgraph-clj           StateGraph / checkpoint / create-react-agent
  └─ langchain-clj           models / tools / messages / Datomic-compat store
```

See [`90-docs/adr/2606250956-browser-agent-clj-genspark-style-super-agent.md`](../../../90-docs/adr/2606250956-browser-agent-clj-genspark-style-super-agent.md)
for the full design and [`docs/adr/0001-architecture.md`](docs/adr/0001-architecture.md)
for the genspark → browser-agent-clj mapping.

```
src/browseragent/
  run.cljc          top-level entry — the one place host capabilities are injected
  planner.cljc      plan-and-execute: task → :plan/* datoms (+ replan)
  supervisor.cljc   Mixture-of-Agents StateGraph: route → delegate → aggregate
  fleet.cljc        sub-agents: web / research / coder / author
  memory.cljc       semantic memory + audit queries (facts/artifacts/delegations)
  schema.cljc       the whole runtime as a Datomic schema
  events.cljc       UI event projection for host-owned front-ends
  browser/
    provider.cljc   default owned-browser providers (mock / playwright / in-browser / cdp)
    session.cljc    managed browser: owns the session as :browser/* datoms
    live.cljc       stream the agent's browser to the UI + take-over latch
ui/                 static host-adapter placeholder; no bundled cljs build
```

## Design

- **The agent owns its browser.** browser-use-clj keeps `IBrowser` a
  pure injected capability; this repo ships the *default* — if you
  inject nothing the agent launches and owns a browser with its own
  profile/cookies/tabs (`browser/provider`), persists that session as
  `:browser/*` datoms (`browser/session`), and streams frames to a
  live view you can watch and **take over** (`browser/live`). The mock
  provider gives a pure-data browser for tests/offline.

- **Mixture-of-Agents.** `supervisor` is a langgraph `StateGraph` that
  routes each plan step to a sub-agent — by the planner's `:assignee`
  or an injected `:router` (cheap model routes, strong model handles
  the hard step) — runs it, records the decision as a `:deleg/*`
  datom, and finally `:aggregate`s the results into one answer
  (optionally cross-checked by an `:aggregator-model`). Models are the
  `langchain.model/ChatModel` abstraction, so Anthropic / others /
  local are swapped per role via `:models {:router … :web … :critic …}`.

- **Plan-and-execute.** `planner` decomposes the task into ordered
  steps (`:plan-fn` or a planner `:model`) and persists them; replans
  append, so `langchain.db/as-of` shows how the plan evolved.

- **Everything is a datom.** The task, the browser session, the plan,
  every delegation, every sub-agent action (via browser-use-clj's
  action log), semantic memory and generated artifacts are all datoms.
  *"Every URL this task visited"*, *"which tabs is the agent looking
  at"*, *"how many times did we replan"* are Datalog one-liners, and
  the whole run time-travels — the audit/reproducibility a black-box
  super-agent can't give you.

## Quickstart (offline, no API key, no real browser)

```clojure
(require '[browseragent.run :as run]
         '[langchain.model :as model]
         '[langchain.message :as msg])

(run/run
 {:task "Research the price of Example Shop and write a one-page report."
  :models  {:web web-model :research research-model :author author-model}
  :browser {:kind :mock :site site :start-url "https://shop.example"}
  :plan-fn (constantly [{:goal "find the price"      :assignee :web}
                        {:goal "synthesize a summary" :assignee :research}
                        {:goal "write the report"     :assignee :author}])
  :search-fn (fn [q] …) :fetch-fn (fn [url] …)})
;; => {:result … :plan … :results … :facts … :artifacts … :urls … :conn …}
```

Run the bundled mock demo (prints the event stream + the Datomic audit
trail):

```sh
kbb -M:dev:run
```

## Going live

- **Models** — swap the mock models for `langchain.model/anthropic-model`
  (inject `:http-fn` / `:json-read` / `:json-write` host fns).
- **Owned browser** — add a `raw-browser` `:playwright` defmethod
  (sketch in `browser/provider.cljc`, behind the `:playwright` alias):
  a persistent Chromium context = the agent's own profile. `in-browser`
  drives an agent-owned tab from the cljs UI; `cdp` talks to a remote
  browser (kotoba-WASM host).
- **Live view / take-over** — pass `:live {:emit-fn … :screenshot-fn …
  :takeover (atom false)}`; frames stream to the UI and flipping
  `:takeover` yields to the human via a langgraph interrupt.
- **Tools at scale** — concatenate more tool maps onto a sub-agent, or
  bridge an MCP server's `list_tools`/`call_tool` into `langchain.tool`.

## Tests

```sh
kbb -M:test     # end-to-end run on mocks + Datalog/time-travel assertions
```

## License

MIT © 2026 Jun Kawasaki
