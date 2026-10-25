(ns task-graph.langgraph
  "Optional convenience: compile a task-graph catalog+ledger into a
  kotoba-lang/langgraph `langgraph.graph` state-graph, for callers that want
  an in-process graph rather than driving task-graph.core/ready-tasks
  directly from an external scheduler.

  This is NOT the primary integration path — local-manimani-cdci's Phase 3
  (ADR-2607202800 in com-junkawasaki/root) drives task-graph.core/ready-tasks
  straight from a `config/repo-loops.edn` :command script and dispatches via
  the existing `manimani.work` WorkItem lifecycle (propose -> govern ->
  execute), reusing that Governor rather than this namespace. Use this
  namespace only when an in-process langgraph run is genuinely what a caller
  wants (e.g. composing task-graph readiness as one step inside a larger
  StateGraph).

  The graph is intentionally single-node: :compute-ready reads {:catalog
  :ledger} from state and emits {:ready (ready-tasks catalog ledger)}. This
  library never mutates the ledger or dispatches work itself — the node only
  ever proposes a ready-set, matching the actor Governor pattern (see
  .claude/skills/build-actor in com-junkawasaki/root) where an
  intelligence/compute node proposes and a separate Governor commits."
  (:require [task-graph.core :as core]
            [langgraph.graph :as g]))

(defn ->state-graph
  "Returns a compiled langgraph graph. (g/invoke compiled {:catalog c
   :ledger l}) => {:catalog c :ledger l :ready [...]}. `opts` is passed
   through to g/compile-graph (e.g. {:recursion-limit n})."
  [& [opts]]
  (-> (g/state-graph {:channels {:catalog {:reducer (fn [_ new] new) :default []}
                                  :ledger {:reducer (fn [_ new] new) :default []}
                                  :ready {:reducer (fn [_ new] new) :default []}}})
      (g/add-node :compute-ready
                  (fn [state] {:ready (core/ready-tasks (:catalog state) (:ledger state))}))
      (g/set-entry-point :compute-ready)
      (g/set-finish-point :compute-ready)
      (g/compile-graph (or opts {}))))
