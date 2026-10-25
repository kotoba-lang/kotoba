# kotoba-taskdag

Pure `.cljc` projector for EDN task-dependency graphs: given a topology
**base catalog** (`{:task/id :task/requires [...] ...}` entries) and an
append-only **progress ledger** (`{:task/id :event/type :event/seq ...}`
event maps), compute which tasks are currently **ready** (every requirement
completed, task itself not yet terminal).

```clojure
(require '[task-graph.core :as task-graph])

(def catalog
  [{:task/id "A" :task/requires []}
   {:task/id "G" :task/requires []}
   {:task/id "E" :task/requires ["G"]}
   {:task/id "B" :task/requires ["G"]}])

(def ledger
  [{:task/id "A" :event/seq 1 :event/type :completed}])

(task-graph/ready-tasks catalog ledger)
;; => ({:task/id "G", :task/requires [], :task/status :ready})
```

`task-graph.core` has zero I/O and zero dependencies — it does not read
files, does not know about GitHub, and does not dispatch anything. Callers
own loading the catalog/ledger, deciding what "dispatch" means, gating
dispatch through a Governor/HITL check, and appending the resulting event.

`task-graph.langgraph` is an optional wrapper that compiles the same logic
into a [kotoba-lang/langgraph](https://github.com/kotoba-lang/langgraph)
`state-graph`, for callers who want an in-process graph node rather than
driving `ready-tasks` from an external scheduler directly.

## Origin

Built as Phase 2 of ADR-2607202800 in
[com-junkawasaki/root](https://github.com/com-junkawasaki/root)
(`90-docs/adr/2607202800-task-graph-edn-schema-kotoba-langgraph-integration.edn`),
which also defines the EDN schema this library operates over
(`90-docs/task-graphs/task-graph.datoms.edn` + `task-graph-ledger.edn`) and
the reference I/O shell (`scripts/task-graph-query.cljs`,
`scripts/task-graph-ledger-append.cljs`). Phase 3 (same ADR) wires this into
`local-manimani-cdci`'s `config/repo-loops.edn` scheduler, dispatching ready
tasks through `manimani.work`'s existing WorkItem propose/govern/execute
lifecycle rather than a new gate.

## Test

```sh
kbb -M:test
```
