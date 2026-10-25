(ns lg-curpus2skill.graphs.health
  "curpus2skill `health` graph — liveness ping.

  Faithful clj port of the Python `_make_health_graph()` in
  `lg/lg_curpus2skill/server.py` (ADR-2606280030).

  Topology: START → ping → END. The `ping` node returns the service status map
  (mirrors the Python `{\"status\": \"ok\", \"service\": \"lg-curpus2skill\"}`)."
  (:require [langgraph.graph :as g]))

(defn node-ping
  "Liveness node — returns the service status (Python `_node` parity)."
  [_state]
  {:result {:status "ok" :service "lg-curpus2skill"}})

(defn build
  "Compile the health StateGraph (START → ping → END)."
  []
  (-> (g/state-graph)
      (g/add-node :ping node-ping)
      (g/set-entry-point :ping)
      (g/set-finish-point :ping)
      (g/compile-graph)))

(def GRAPH (build))
