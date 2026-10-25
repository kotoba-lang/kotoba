(ns lg.lg-kyber.server
  "lg-kyber server surface — clj port of the host-independent core of server.py
  (the GRAPHS registry + the POST /runs dispatch + /health payload + the cron schedule
  table). The FastAPI/apscheduler/asyncpg-pool host wiring has no bb equivalent and is
  out of scope for the port (server.py stays the live entrypoint); this ns gives the
  registry + dispatcher a runnable clj home that the ported graphs plug into.

  `ported-graphs` is the SUBSET migrated to langgraph-clj so far; `all-graph-ids` keeps
  parity with server.py's GRAPHS dict (the rest still run from .py — coexist)."
  (:require [langgraph.graph :as g]
            [lg.lg-kyber.graphs.health :as health]
            [lg.lg-kyber.graphs.metrics-daily :as metrics-daily]
            [lg.lg-kyber.graphs.business-operating-react :as bo-react]))

(def ported-graphs
  "graph-id → compiled langgraph-clj graph (the clj-ported subset)."
  {"health"                   health/graph
   "metrics_daily"            metrics-daily/graph
   "business_operating_react" bo-react/graph})

(def all-graph-ids
  "Full registry, parity with server.py GRAPHS (ids still .py-only are noted in PR/coexist)."
  ["health" "bmc_iteration" "bmc_agent" "lead_discovery" "activation" "conversion"
   "retention" "marketing" "sales" "metrics_daily" "business_operating"
   "business_operating_react"])

(def cron-schedule
  "Port of the server.py cron table (all JST) as data."
  [{:graph "metrics_daily"            :cron "09:00 daily"}
   {:graph "bmc_agent"                :cron "09:03 daily"}
   {:graph "bmc_iteration"            :cron "16:00 daily"}
   {:graph "activation"               :cron "08:30 daily"}
   {:graph "conversion"               :cron "10:15 daily"}
   {:graph "retention"                :cron "11:00 daily"}
   {:graph "lead_discovery"           :cron "00,06,12,18:00"}
   {:graph "marketing"                :cron "00,06,12,18:05"}
   {:graph "sales"                    :cron ":15 hourly"}
   {:graph "business_operating_react" :cron "06:00 daily"}])

(defn health-response
  "Port of GET /health|/ok payload (ts is :clj-only)."
  []
  {"ok" true "app" "lg-kyber"
   "ts" #?(:clj (System/currentTimeMillis) :default 0)
   "graphs" all-graph-ids})

(defn dispatch
  "Port of POST /runs core: look up a graph by id and invoke it. Body is a string-keyed
  map {\"graph\"|\"assistant_id\" id, \"input\" m}. Returns {\"ok\" true \"graph\" id
  \"result\" final-state} or a 404-shaped {\"ok\" false \"error\" …} for an unknown /
  not-yet-ported id. `input` may carry the injected :db-api / :llm-api ports."
  [body]
  (let [graph-id (or (get body "graph") (get body "assistant_id"))
        input (or (get body "input") {})]
    (if-let [cg (get ported-graphs graph-id)]
      {"ok" true "graph" graph-id "result" (g/invoke cg input)}
      {"ok" false
       "error" (if (some #{graph-id} all-graph-ids)
                 (str "graph not yet ported to clj (runs from .py): " graph-id)
                 (str "unknown graph: " graph-id))})))
