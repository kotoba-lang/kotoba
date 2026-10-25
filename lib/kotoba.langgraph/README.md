# langgraph

LangGraph-style graph orchestration in **portable Clojure** — every
namespace is `.cljc`, designed to run on **Clojure-on-WASM hosts**
(SCI, ClojureScript, GraalVM, kotoba-clj) as well as the JVM, with all
state persisted through a **Datomic API**.

Built on [langchain](https://github.com/kotoba-lang/langchain)
(Runnables/LCEL, messages, prompts, models, tools, memory, and the
Datomic-compatible store) — the same layering as upstream
langchain-core / langgraph. langchain is the only dependency, and
it is itself zero-dep.

```
src/langgraph/
  graph.cljc       StateGraph + Pregel superstep loop + interrupts
  core.kotoba      the same superstep loop as a Kotoba template module,
                   compiled by amu to a native binary (see below)
  checkpoint.cljc  checkpointers (in-memory / Datomic) — resume & time travel
  prebuilt.cljc    create-react-agent
  agent_loop.cljc  provider-neutral model -> tools -> results turn reducer
  viz.cljc         graph → Mermaid
```

## Design

- **WASM premise** — no JVM interop, no threads, no wall clock. No
  I/O in the library: HTTP and JSON are *injected host capabilities*
  (see langchain's `anthropic-model`).
- **Datomic API premise** — checkpoints are datoms. Graph execution
  history becomes a queryable fact log — resume, human-in-the-loop,
  time travel, and audits are Datalog queries (ADR-0010 pattern).
  Real Datomic Local or DataScript drops in via the
  `langchain.db/api` function map.
- **Durable loop boundary** — long-running agents are modeled as a host
  supervisor repeatedly running bounded StateGraph ticks. The host owns
  leases, sleep/cadence, crash recovery, budgets, and worker lifecycle;
  the graph owns one auditable step with checkpoint/interrupt support.

Which upstream document each namespace mirrors — with the URL that was
actually fetched, and when — is pinned in
[docs/catalog.edn](docs/catalog.edn) (shape enforced by
`test/langgraph/catalog_test.cljk`).

## Quickstart

Running one behind a supervisor rather than reading the API? Start with
[docs/operator-quickstart.md](docs/operator-quickstart.md) — the four
runtime behaviours that surprise hosts, each with a command that shows it.

```clojure
;; deps.edn
;; {:deps {io.github.kotoba-lang/langgraph {:git/tag "v0.2.0" :git/sha "…"}}}

(require '[langgraph.graph :as g]
         '[langgraph.prebuilt :as prebuilt]
         '[langgraph.checkpoint :as cp]
         '[langchain.model :as model]
         '[langchain.message :as msg]
         '[langchain.db :as db])

;; --- a graph with reducer channels, conditional edges, interrupts ---
(def graph
  (-> (g/state-graph {:channels {:messages {:reducer into :default []}}})
      (g/add-node :draft (fn [s] {:messages [(msg/ai "draft…")]}))
      (g/add-node :send  (fn [s] {:messages [(msg/ai "sent")]}))
      (g/set-entry-point :draft)
      (g/add-edge :draft :send)
      (g/compile-graph
       {:checkpointer (cp/datomic-checkpointer (db/create-conn cp/checkpoint-schema))
        :interrupt-before #{:send}})))   ; human-in-the-loop

(g/run* graph {:messages [(msg/user "hello")]} {:thread-id "t1"})
;; => {:status :interrupted …}  — review, optionally edit:
(g/update-state! graph "t1" {:messages [(msg/user "approved")]})
(g/run* graph nil {:thread-id "t1"})     ; resume
;; => {:status :done …}

;; --- ReAct agent ---
(def agent
  (prebuilt/create-react-agent
   {:model (model/anthropic-model
            {:api-key API-KEY
             :model "claude-opus-4-8"
             :http-fn host-fetch          ; injected host capability
             :json-write … :json-read …}) ; defaults to js/JSON on cljs
    :tools [{:name "get_weather"
             :description "Get current weather for a location"
             :schema {:type "object"
                      :properties {:location {:type "string"}}
                      :required ["location"]}
             :fn (fn [{:keys [location]}] …)}]}))

(g/invoke agent {:messages [(msg/user "Weather in Paris?")]})
```

Checkpoints are plain datoms, so execution history is queryable:

```clojure
(db/q '[:find ?thread (max ?step)
        :where [?c :checkpoint/thread ?thread]
               [?c :checkpoint/step ?step]]
      (db/db conn))
```

## Kotoba core — compiled to a native binary

`src/langgraph/core.kotoba` is `langgraph.graph`'s superstep loop written
in Kotoba as a **template module over the application's state record**:
`(ns langgraph.core (:params [state]))`. An application binds the state
type and supplies its nodes as closures; amu compiles the closed graph to
`aarch64-macos` / `x86_64-linux` (and wasm32 / js / the KIR interpreter —
the same source, every target):

```clojure
(ns my.app
  (:require [langgraph.core :as lg :with {state [:record :my.app/S [[:count :i64]]]}])
  (:export [main]))
(defrecord S [count :i64])
(defn- bump [id :i64 step :i64 s [:record :my.app/S [[:count :i64]]]] [:record :my.app/S [[:count :i64]]]
  (->S (+ (:count s) 1)))
(defn main [] :i64
  (let [g (lg/graph (lg/pack-conj (lg/pack-empty) 0) 25 0 0 1)   ; entry [0], limit 25, no interrupts, 1 node
        ck (lg/run g (vector-new) (fn [id step s] (bump id step s)) (fn [id s] (lg/pack-conj (lg/pack-empty) (lg/end-id))) (lg/start g (->S 0)))]
    (:count (lg/ck-st ck))))
```

```sh
amu compile my/app.kotoba --jvm-free --source-path src --target aarch64-macos --output app.kexe
amu extract-native app.kexe --symbol main --output main.bin   # then tools/kexe_loader
```

What is the same as `langgraph.graph`: static and conditional edges,
fan-out in insertion order with a distinct frontier, the recursion
limit, `interrupt-before` / `interrupt-after`, resume, `update-state!`
(`with-state`), running a finished thread again. What is data instead of a
protocol: the checkpoint (`Ckpt {st step frontier status}`) is a value in
and out — persistence, `list-checkpoints`, time travel are the host's,
exactly as the checkpointer stores here are host adapters. What is a
`:status` instead of a throw: `:recursion-limit`, `:unknown-node`,
`:no-entry`, and `:frontier-overflow` (more than 8 successors in one
superstep — the ceiling the native target's word-only records impose today,
named in the module header with the rest of them).

Parity is measured, not claimed: the nine scenarios in
`test/langgraph/kotoba/scenarios.kotoba` fold their final checkpoint into
one i64 each; `test/langgraph/core_parity_test.cljk` runs the same nine
through `langgraph.graph` and must reach the same numbers
(`test/langgraph/kotoba/expected.edn`); `scripts/verify-kotoba-core.cljk`
runs the guest on the interpreter, wasm32 and js (`amu test --source-path
src`) and **executes** each scenario as a native binary through amu's kexe
loader:

```sh
kbb --backend sci scripts/verify-kotoba-core.cljk     # AMU=<path to amu/bin/amu> if amu is not the west sibling
```

It needs amu at ADR 0350 or later (amu #996: `amu test --source-path`, closures
in read-back artifacts, and the kotoba-sema / kotoba-script pins that port
measured its way to).

## Mapping from upstream

See [docs/adr/0001-architecture.md](docs/adr/0001-architecture.md) for
the full LangGraph → langgraph correspondence table and the
injected-I/O rationale. The LangChain layer lives in
[langchain](https://github.com/kotoba-lang/langchain).

## Tests / example

```sh
kbb -M:test     # 29 tests, 92 assertions (graph / checkpoint / agent layer)
kbb -Sdeps '{:paths ["src" "examples"]}' \
        -M -e "(require 'react-agent) (react-agent/-main)"
```

The example runs offline against a mock model — no API key needed.

Workspace development against a local langchain checkout:
`kbb -M:dev:test`.
