# langchain-clj

LangChain-core-style LLM foundation layer in **portable Clojure** —
no third-party dependencies (only kotoba-lang standard libraries), every
namespace is `.cljk` (renamed from `.cljc` on 2026-09-11), designed to run on
**Clojure-on-WASM hosts** (SCI, ClojureScript, GraalVM, kotoba-clj) as
well as the JVM, with all state persisted through a **Datomic API**.

[langgraph-clj](https://github.com/kotoba-lang/langgraph)
builds graph orchestration (StateGraph, checkpointers, ReAct agent) on
top of this library — the same layering as upstream langchain-core /
langgraph.

```
src/langchain/
  runnable.cljk    LCEL Runnables: pipe / parallel / branch / retry / fallbacks
  message.cljk     chat message data model (Anthropic-shaped maps)
  prompt.cljk      {var} templates, chat templates, placeholders
  model.cljk       ChatModel protocol, mock model, Anthropic + OpenAI-compatible
                   adapters (OpenAI / Ollama / Gemini; I/O injected)
  tool.cljk        tool definitions + execution + wire-format conversion
  parser.cljk      str / edn / json output parsers
  memory.cljk      chat history as datoms
  db.cljk          Datomic-API-compatible EAV store + Datalog + pull (swappable)
  repo_profile.cljk machine-checkable local-query/encrypted-publish contract
```

## Design

- **WASM premise** — no JVM interop, no threads, no wall clock. The
  library does no I/O: HTTP and JSON are *injected host capabilities*
  (fetch on a WASM host, any client on the JVM).
- **Datomic API premise** — chat history is datoms. A minimal
  Datomic-compatible store (datalog `q`, `pull`, upsert,
  cardinality-many, lookup refs, `as-of`) is bundled; real Datomic
  Local or DataScript drops in via the `langchain.db/api` function
  map. Cross-thread views are Datalog queries (ADR-0010 pattern).
- **Repository-driven Agent premise** — cloud-itonami, actors and artificial
  organisms declare `langchain.repo-profile`. Private EDN is queried locally;
  only Kagi-sealed chunks and Kotobase heads may enter DataLad/remotes. An
  explicitly classified public fact repository is the narrow exception.

## Quickstart

```clojure
(require '[langchain.runnable :as r]
         '[langchain.prompt :as prompt]
         '[langchain.parser :as parser]
         '[langchain.model :as model]
         '[langchain.message :as msg])

;; LCEL — plain fns, keywords, and maps are already Runnables
(def claude
  (model/anthropic-model
   {:api-key API-KEY
    :model "claude-opus-4-8"
    :http-fn host-fetch            ; injected host capability
    :json-write … :json-read …}))  ; defaults to js/JSON on cljs

;; or any OpenAI-compatible backend — OpenAI, local Ollama, Gemini:
(def gemma
  (model/openai-model
   {:url "http://localhost:11434/v1/chat/completions"   ; Ollama, no api-key
    :model "hf.co/unsloth/gemma-4-E4B-it-qat-GGUF:UD-Q4_K_XL"
    :http-fn host-fetch
    :json-write … :json-read …}))

(def chain
  (r/pipe (prompt/chat-template
           [:system "You translate to {lang}."]
           [:placeholder :history]
           [:user "{text}"])
          (model/as-runnable claude)
          (parser/str-parser)))

(r/invoke chain {:lang "French" :text "hello" :history []})

;; tool calling
(def weather
  {:name "get_weather"
   :description "Get current weather for a location"
   :schema {:type "object"
            :properties {:location {:type "string"}}
            :required ["location"]}
   :fn (fn [{:keys [location]}] …)})

(model/-generate (model/bind-tools claude [weather])
                 [(msg/user "Weather in Paris?")] {})
;; => {:role :assistant :tool-calls [{:id … :name "get_weather" …}] …}

;; chat history as datoms
(require '[langchain.memory :as memory] '[langchain.db :as db])
(def conn (db/create-conn memory/memory-schema))
(def hist (memory/datomic-chat-history conn))
((:append! hist) "thread-1" (msg/user "hello"))
(db/q '[:find ?tid (count ?m)
        :where [?t :thread/id ?tid] [?m :msg/thread ?t]]
      (db/db conn))

;; JVM repository host: keep the query view local and editable as EDN.
;; The repository publisher encrypts this state.edn only when it is pushed.
(require '[langchain.edn-persist :as edn-persist]
         '[langchain.persist :as persist])
(def durable-conn
  (db/create-conn memory/memory-schema
                  (persist/scoped
                   (edn-persist/host "workspace/did_example/state.edn")
                   "chat/main")))

;; Production actor entrypoints share KOTOBA_REPOSITORY_STATE_FILE and may
;; override their default stream with KOTOBA_REPOSITORY_STREAM.
(def deployed-conn
  (db/create-conn memory/memory-schema
                  (edn-persist/required-persist-from-env "chat/main")))
```

## Mapping from upstream

See [docs/adr/0001-architecture.md](docs/adr/0001-architecture.md) for
the langchain-core → langchain-clj correspondence table and the
zero-dependency / injected-I/O rationale.

That table names upstream constructs; [docs/catalog.edn](docs/catalog.edn)
gives each of them an address — the document that was actually fetched, its
final status and the date, next to the file here that mirrors it. It also
covers the wire formats and the Datomic API this library reimplements, which
the table does not. `test/langchain/catalog_test.cljk` keeps it honest: every
row must carry a successful fetch and a date, every `:mirrors` path must
exist, URLs must be distinct, and every namespace that is a port of something
must appear.

## Tests / example

```sh
kbb -M:test                                  # JVM: 156 tests, 543 assertions
bin/test-portable-cljs                           # ClojureScript: 40 tests, 249 assertions
kbb -Sdeps '{:paths ["src" "examples"]}' \
        -M -e "(require 'chain) (chain/-main)"   # offline, mock model
kbb -Sdeps '{:paths ["src" "examples"]}' \
        -M -e "(require 'live-murakumo) (live-murakumo/-main)"   # real model
```

Both counts measured 2026-09-07. `test/langchain/db_contract_test.cljk` holds
the `langchain.db` invariants the rest of the suite does not discriminate:
that a `:db.unique/identity` attribute resolves an upsert no matter where in
the map it was written, that replacing a value records the retraction in
`:tx-data` so `as-of` can replay it, and that an entity with no unique
attribute gets a fresh identity instead of merging into an existing one.
Each was watched go red against a deliberately broken `db.cljc` before it
landed, and each mutation was first confirmed to leave the previous suite
entirely green — 153 tests / 535 assertions, once per mutation. The
mutations live in the superproject's `scripts/maturity-loop/mutations.edn`
under suite `orgs/kotoba-lang/langchain`.

That namespace is the first db-layer one the ClojureScript runner executes.
`langchain.db` is `.cljc` and is what `langchain-store` — and through it the
316 `cloud-itonami` repositories depending on that wrapper — reaches for, but
until now only the JVM had ever run it. The `:langchain/entity-map-loses-unique-first-ordering`
mutation was confirmed to go red on both runtimes with the same two
assertions, so the second runtime is a gate rather than a re-run.

New here? [docs/operator-quickstart.md](docs/operator-quickstart.md) walks the
five steps in order — resolve deps, test, run offline, call a real model
through the injected-I/O seam, and make chat history durable across processes —
showing the actual output of each, plus the two failure modes that look like
bugs and aren't.
