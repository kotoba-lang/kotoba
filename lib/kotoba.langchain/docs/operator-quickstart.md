# Operator quickstart

Five steps, in order, each one command. They were all run on a clean checkout
before this file was written, and the output shown under each is the real
output, not an illustration. If a step does not produce something close to
what is shown, stop there — the later steps assume the earlier ones worked.

The README's Quickstart shows the *API*. This shows the *path*: what to run,
in what order, what you should see, and what goes wrong.

Prerequisites: a JVM (17+) and the `clojure` CLI. Nothing else — the library
has no third-party runtime dependency (ADR-0001), and step 4 reaches the
network without adding an HTTP client.

---

## 1. Resolve dependencies

```sh
clojure -P -M:test
```

Silent, exit 0. This is the step that proves your toolchain can reach the one
first-party git dependency (`io.github.kotoba-lang/json`) plus the test-only
deps. A first run downloads them into `~/.gitlibs` and `~/.m2` and takes a
while; afterwards it returns immediately.

Do this before step 2 so that a network or credential failure shows up as
itself, rather than as a confusing test error.

## 2. Run the tests

```sh
kbb -M:test
```

```
Ran 156 tests containing 543 assertions.
0 failures, 0 errors.
```

This is the whole suite, `.cljc` and JVM-only alike, and it is expected to be
fully green — if you are about to change something, run this first so you can
tell your failures from pre-existing ones.

The `.cljc` half has a second gate, and it is not the same run:

```sh
bin/test-portable-cljs
```

```
portable cljc — 40 tests, 249 assertions, 0 failures, 0 errors, on ClojureScript
```

It needs `nbb` on `PATH` and no `deps.edn` resolution at all. Run it when you
touch anything under `src/` that is `.cljc` — `langchain.db` included, whose
contract tests are in both runs and have been confirmed to discriminate in
both.

## 3. Run the example offline

```sh
kbb -Sdeps '{:paths ["src" "examples"]}' \
        -M -e "(require 'chain) (chain/-main)"
```

```
FR: « hello »
FR: « good night »

history as datoms:
  :user | hello
  :assistant | FR: « hello »
  :user | good night
  :assistant | FR: « good night »

threads in db: #{[demo 4]}
```

No network, no API key: `chain` wires a `mock-model` into a real LCEL pipe
(`prompt → model → parser`) and a real datom-backed chat history. If this
works and step 4 does not, the problem is your network or the model service,
not the library.

## 4. Call a real model

```sh
kbb -Sdeps '{:paths ["src" "examples"]}' \
        -M -e "(require 'live-murakumo) (live-murakumo/-main)"
```

```
resolved via alias: model=murakumo-main alias-for=qwen3.8-27b
reply: "Bonjour"
OK
```

This is the step worth reading the source of (`examples/live_murakumo.cljk`,
~120 lines). langchain performs no I/O itself, so everything host-shaped is
injected there and nowhere in the library:

| seam | supplied by the example |
|---|---|
| `:http-fn` | `java.net.http` — about 20 lines, no `http-kit`, no added dep |
| `:json-write` | `langchain.json/encode` |
| `:json-read` | `langchain.json/decode` **plus a keywordize walk** |

**The keywordize step is required, not cosmetic.** `langchain.json/decode`
returns string keys, while `model/parse-openai-response` reads `:choices`,
`:message`, `:content`. Passing `decode` in directly gets you an exception
about no choices in the response, on a response that in fact had choices.

The model id is resolved at run time from the `murakumo-main` KV alias and is
deliberately not hardcoded — fleet main is swapped by rewriting that one
entry, so a baked-in id goes stale silently. Resolution order:

1. `MURAKUMO_URL` + `MURAKUMO_MODEL` if both are set (prints `resolved via env`)
2. the alias at `https://api.murakumo.cloud/infer/models/murakumo-main`
3. endpoint-only fallback — an endpoint, never an id, because whatever that
   endpoint serves is current by construction

To point the same chain at anything else OpenAI-compatible (a local Ollama, a
vLLM, OpenAI itself), set those two variables:

```sh
MURAKUMO_URL=http://localhost:11434/v1/chat/completions \
MURAKUMO_MODEL=your-model-here \
kbb -Sdeps '{:paths ["src" "examples"]}' \
        -M -e "(require 'live-murakumo) (live-murakumo/-main)"
```

### If `reply` comes back `""`

Not a failure of the wiring. Current fleet main is a reasoning model: it
spends tokens on `reasoning_content` before emitting any `content`, and the
OpenAI-shaped adapter reads only `content`. Too small a `:max-tokens` budget
therefore returns `finish_reason: "length"` with `content: ""` — an empty
string, **not** an error status, so nothing throws. The example uses 512 and
exits non-zero with an explanation if it still lands empty.

## 5. Make the chat history durable

Chat history is datoms, and a connection persists through an injected
persistence map. The production entrypoint takes its coordinates from the
environment, so run it twice — write in one process, recover in another:

```sh
export KOTOBA_REPOSITORY_STATE_FILE=/tmp/lc-state.edn

kbb -M -e "
(require '[langchain.db :as db] '[langchain.memory :as memory]
         '[langchain.message :as msg] '[langchain.edn-persist :as ep])
(def conn (db/create-conn memory/memory-schema (ep/required-persist-from-env \"chat/main\")))
(def hist (memory/datomic-chat-history conn))
((:append! hist) \"t1\" (msg/user \"remember me\"))
(println \"wrote:\" (count ((:messages hist) \"t1\")) \"message(s)\")"

kbb -M -e "
(require '[langchain.db :as db] '[langchain.memory :as memory] '[langchain.edn-persist :as ep])
(def conn (db/create-conn memory/memory-schema (ep/required-persist-from-env \"chat/main\")))
(def hist (memory/datomic-chat-history conn))
(println \"recovered:\" (pr-str (mapv (juxt :role :content) ((:messages hist) \"t1\"))))
(println \"datalog:\" (pr-str (db/q '[:find ?tid (count ?m)
                                      :where [?t :thread/id ?tid] [?m :msg/thread ?t]]
                                    (db/db conn))))"
```

```
#'user/conn
#'user/hist
0
wrote: 1 message(s)
```
```
#'user/conn
#'user/hist
recovered: [[:user "remember me"]]
datalog: #{["t1" 1]}
```

`kbb -M -e` prints the value of every top-level form, so the `#'user/…`
lines and the bare `0` (what `append!` returned) are the runner echoing, not
output of yours. The lines that matter are the last one of each.

The state file is a readable EDN transaction log, one stream per key:

```clojure
#:kotoba.agent{:sequence 1,
               :streams {"chat/main" [{:tx 1,
                                       :tx-data [[:db/add 1 :thread/id "t1"] ...],
                                       :seq 1}]}}
```

`KOTOBA_REPOSITORY_STATE_FILE` is **required** — with it unset,
`required-persist-from-env` throws
`:langchain.edn-persist/state-file-required` rather than silently starting an
in-memory connection that loses everything on exit. `KOTOBA_REPOSITORY_STREAM`
overrides the default stream (`"chat/main"` above) when one state file carries
several.

---

## Where to go next

- `docs/adr/0001-architecture.md` — the langchain-core → langchain-clj
  correspondence table, and why I/O is injected rather than depended on.
- `langchain.jvm` — a batteries-included JVM host-fn (http-kit + jsonista)
  if you would rather not hand-roll step 4's `:http-fn`. It is behind
  `#?(:clj ...)` and its deps stay out of the main `:deps` on purpose, so
  bring your own `http-kit`/`jsonista`.
- [langgraph-clj](https://github.com/kotoba-lang/langgraph) — StateGraph,
  checkpointers, and the ReAct agent, built on this layer.

## Scope of this document

Every command above was executed on JVM Clojure on macOS/arm64 immediately
before this file was committed. The library is `.cljc` throughout and is
designed for ClojureScript, SCI and Clojure-on-WASM hosts as well, but **those
hosts are not exercised by this quickstart** — on them, steps 1–3 differ and
step 4's injected seams are the host's `fetch` and `js/JSON`.
