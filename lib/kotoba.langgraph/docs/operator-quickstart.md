# Operator quickstart

For the person who has to **run** a langgraph graph — behind a supervisor,
a queue, a cron, an HTTP handler — rather than the person reading the API.
Everything below runs offline; no API key, no model provider.

The README describes the shape of the library. This describes the four
things it does at runtime that will surprise you, and the commands that
show each one. Every command and every block of output on this page was
executed against this checkout; §5's claims are pinned by
[`test/langgraph/operator_quickstart_test.cljk`](../test/langgraph/operator_quickstart_test.cljk)
so they cannot rot silently.

---

## 0. Prerequisites

The Clojure CLI and a JVM. Verified with:

```
$ clojure --version
Clojure CLI version 1.12.5.1654
$ java -version
openjdk version "24.0.2" 2025-07-15
```

Network access is needed on the first command only, to fetch the single
git dependency (`kotoba-lang/langchain`). After that everything is local.

## 1. Confirm the checkout is green

```
$ kbb -M:test
Ran 29 tests containing 92 assertions.
0 failures, 0 errors.
```

If this is red, stop here — nothing below is diagnosable until it is green.

## 2. Run an agent end to end, offline

`examples/react_agent.cljk` wires a mock model, a tool, and a
Datomic-backed checkpointer, so a full ReAct loop runs with no network:

```
$ kbb -Sdeps '{:paths ["src" "examples"]}' \
    -M -e "(require 'react-agent) (react-agent/-main)"
flowchart TD
  START([start])
  END([end])
  agent["agent"]
  tools["tools"]
  START --> agent
  tools --> agent
  agent -.->|condition| END

→ :agent |
→ :tools | 72F and sunny in Paris
→ :agent | It is 72F and sunny in Paris.

checkpoints as datoms: 3
final answer: It is 72F and sunny in Paris.
```

Three supersteps, three checkpoints. The empty first line is the model's
tool-call message, which carries no text content.

## 3. Interrupt, inspect, edit, resume

This is the whole human-in-the-loop cycle. Save as `tour.clj` and run it
with `kbb -Sdeps '{:paths ["src"]}' -M tour.clj`:

```clojure
(require '[langgraph.graph :as g]
         '[langgraph.checkpoint :as cp]
         '[langgraph.viz :as viz]
         '[langchain.message :as msg]
         '[langchain.db :as db])

;; A two-node approval graph. :send is gated: nothing sends without a human.
(def conn (db/create-conn cp/checkpoint-schema))
(def cpr  (cp/datomic-checkpointer conn))

(def approval
  (-> (g/state-graph {:channels {:messages {:reducer (fnil into []) :default []}}})
      (g/add-node :draft (fn [_] {:messages [(msg/ai "Dear customer, ...")]}))
      (g/add-node :send  (fn [_] {:messages [(msg/ai "SENT")]}))
      (g/set-entry-point :draft)
      (g/add-edge :draft :send)
      (g/set-finish-point :send)
      (g/compile-graph {:checkpointer cpr :interrupt-before #{:send}})))

(println "== the graph ==")
(println (viz/mermaid approval))

(println "\n== tick 1: runs :draft, stops at the gate ==")
(let [r (g/run* approval {:messages [(msg/user "refund request")]} {:thread-id "t1"})]
  (println "status  :" (:status r))
  (println "frontier:" (:frontier r) " <- what will run when you resume")
  (println "messages:" (mapv :content (:messages (:state r)))))

(println "\n== what an operator sees without touching the graph ==")
(println "checkpoints:" (mapv (juxt :step :status) (cp/list-checkpoints cpr "t1")))
(println "latest     :" (select-keys (cp/get-latest cpr "t1") [:step :status :frontier]))

(println "\n== human edits the state, then resumes ==")
(g/update-state! approval "t1" {:messages [(msg/user "approved by ops")]})
(let [r (g/run* approval nil {:thread-id "t1"})]
  (println "status  :" (:status r))
  (println "messages:" (mapv :content (:messages (:state r)))))

(println "\n== time travel: state as of step 1 ==")
(println (select-keys (cp/get-state-at cpr "t1" 1) [:step :status :frontier]))

(println "\n== checkpoints are datoms, so history is a query ==")
(println "threads and their last step:"
         (db/q '[:find ?thread (max ?step)
                 :where [?c :checkpoint/thread ?thread]
                        [?c :checkpoint/step ?step]]
               (db/db conn)))
```

Output:

```
== the graph ==
flowchart TD
  START([start])
  END([end])
  draft["draft"]
  send["send"]
  START --> draft
  draft --> send
  send --> END

== tick 1: runs :draft, stops at the gate ==
status  : :interrupted
frontier: [:send]  <- what will run when you resume
messages: [refund request Dear customer, ...]

== what an operator sees without touching the graph ==
checkpoints: [[1 :interrupted]]
latest     : {:step 1, :status :interrupted, :frontier [:send]}

== human edits the state, then resumes ==
status  : :done
messages: [refund request Dear customer, ... approved by ops SENT]

== time travel: state as of step 1 ==
{:step 1, :status :interrupted, :frontier [:send]}

== checkpoints are datoms, so history is a query ==
threads and their last step: #{[t1 3]}
```

The four operator verbs are all there: `run*` (drive), `list-checkpoints`
/ `get-latest` (inspect), `update-state!` (edit), `get-state-at` (rewind).
None of the inspection verbs run a node.

## 4. Reading history back: the two checkpointers do not agree

`list-checkpoints` returns different shapes depending on the backend,
because `datomic-checkpointer` upserts on `(thread, step)` while
`mem-checkpointer` appends every write:

```
mem-checkpointer     history: [[1 :running] [1 :interrupted] [1 :running] [2 :running] [2 :done]]
datomic-checkpointer history: [[1 :interrupted] [2 :done]]
```

Both ran the identical two ticks. Consequences you have to design around:

- **`get-state-at` returns the *first* row it finds for a step.** With
  `mem-checkpointer` that is the earliest intermediate write, not the
  settled one:

  ```
  mem     get-state-at step 1 -> {:step 1, :status :running}     | rows at step 1: 3
  datomic get-state-at step 1 -> {:step 1, :status :interrupted} | rows at step 1: 1
  ```

  If you are rendering "what did this thread look like at step N" to a
  human, use a checkpointer that keeps one row per step, or filter for
  the last one yourself.
- **Step numbers are not dense and not unique.** Do not use `:step` as a
  primary key across backends; `(thread, step)` is one only in the
  Datomic case.

## 5. Before you put this behind a supervisor

Four runtime facts, each pinned by a test in
[`operator_quickstart_test.cljc`](../test/langgraph/operator_quickstart_test.cljk).

### 5.1 `run*` is one tick. It is not "resume until done"

Calling `run*` with `nil` input on a thread whose latest checkpoint is
`:done` does **not** no-op. It starts a fresh tick from the entry point —
which re-arms `interrupt-before`. So the loop alternates forever:

```
call 0 (input {}): status=:interrupted  :send-runs=0
call 1 (input nil): status=:done  :send-runs=1
call 2 (input nil): status=:interrupted  :send-runs=1
call 3 (input nil): status=:done  :send-runs=2
call 4 (input nil): status=:interrupted  :send-runs=2
call 5 (input nil): status=:done  :send-runs=3
call 6 (input nil): status=:interrupted  :send-runs=3
```

The obvious supervisor is therefore wrong:

```clojure
;; WRONG — never terminates, and re-runs the gated node every other call
(while (not= :done (:status (g/run* cg nil {:thread-id tid})))
  (Thread/sleep 1000))
```

Drive it on the checkpoint instead, and decide termination yourself:

```clojure
;; Resume only a thread that is actually parked at a gate.
(when (= :interrupted (:status (cp/get-latest cpr tid)))
  (g/run* cg nil {:thread-id tid}))
```

Polled six times against the same parked thread, that guard resumes once
and then stays quiet:

```
poll 0: resumed=true  :send-runs=1  latest=:done
poll 1: resumed=false  :send-runs=1  latest=:done
poll 2: resumed=false  :send-runs=1  latest=:done
poll 3: resumed=false  :send-runs=1  latest=:done
poll 4: resumed=false  :send-runs=1  latest=:done
poll 5: resumed=false  :send-runs=1  latest=:done
```

This is by design — re-invoking a finished thread is how you run the next
turn of a long-lived agent (ADR-0003's durable outer loop). It is only a
hazard if you mistake `run*` for a resume-to-completion call.

### 5.2 `interrupt-before` gates a checkpoint, not a node

`run*` takes an atomic resume claim only when the checkpointer implements
`ClaimableCheckpointer`. Today exactly one does:

| checkpointer | claims on resume? |
|---|---|
| `cp/mem-checkpointer` | yes |
| `cp/datomic-checkpointer` | **no** |
| `kg-checkpoint`, `kotoba-checkpoint` | **no** |

The claim stops two callers from resuming *the same checkpoint* twice. It
does not stop the gated node from running more than once overall, because
a caller that observes the thread after it reached `:done` legitimately
starts a new tick (§5.1) and re-arms the gate for the next caller.
Measured here with the *claiming* checkpointer — 10 concurrent
`run*`-with-nil callers on one thread-id — the gated node ran 2, 3 or 5
times depending on the interleaving. That number is an observation, not a
guarantee; the point is only that it is never guaranteed to be 1.

**So: serialize per `thread-id` in your host.** A lease, a queue, a
Durable Object, one worker per thread — whatever you already have.
`interrupt-before` is a place to stop, not a mutual-exclusion primitive.

### 5.3 The recursion limit throws; it is not a status

A graph that cycles past `:recursion-limit` (default 25) raises
`ex-info` rather than returning `{:status :limit}`. A supervisor that only
reads `:status` will crash instead of parking the thread:

```
ex-message: Recursion limit reached
ex-data keys: (:frontier :limit :state)
limit: 5  frontier: [:loop]
```

`ex-data` carries the state and the frontier, so you can checkpoint the
failure and show a human where it gave up. Catch it.

### 5.4 The library owns none of your durability

By design (README's WASM premise) there is no wall clock, no threads, no
I/O here. Leases, retries, backoff, budgets, crash recovery and worker
lifecycle are the host's. The graph gives you exactly one auditable step
with a checkpoint at each end.

## 6. Next

- [`docs/adr/0001-architecture.md`](adr/0001-architecture.md) — the
  LangGraph → langgraph correspondence table and the injected-I/O rationale.
- [`docs/adr/0003-coding-agent-turn-loop.md`](adr/0003-coding-agent-turn-loop.md)
  — `langgraph.agent-loop`, the pure reducer for hosts that want to
  interpret effects themselves rather than let the graph call tools.
- `examples/nintendo_loop.cljk` — a longer durable-loop worked example.
