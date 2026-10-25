(ns lgx.server
  "lg-x dispatch core — clj port of the routing logic in `lg_x/server.py`
  (ADR-2606280030).

  The Python module wrapped these graphs in a FastAPI app with /runs, /runs/stream,
  /xrpc/{nsid}, /threads/{tid}/state and /ok //health. This clj port provides the
  framework-independent DISPATCH CORE — the GRAPHS registry, the NSID→assistant map,
  the camelCase→snake_case XRPC input translation, and `run`/`xrpc` invoke helpers —
  as pure, testable functions. The HTTP framing (FastAPI/uvicorn) is intentionally
  NOT ported (deviation): under bb the same surface is served by the kotoba mesh /
  cell-runner or a thin http-kit shim; the load-bearing logic is here. Same graph
  set, same NSID map, same camel→snake translation, same invoke contract.

  State is a clj map (the Python TypedDict). Checkpointing: the Python build used a
  RisingWave-backed AsyncPostgresSaver (`lg_x/checkpointer.py`) — charter-PROHIBITED
  substrate — so this port runs in-memory by default (langgraph-clj's optional
  checkpointer is the swap-in for a kotoba-backed saver)."
  (:require [langgraph.graph :as g]
            [lgx.graphs.health :as health]
            [lgx.graphs.agent-chat :as agent-chat]
            [lgx.graphs.compose-tweet :as compose-tweet]
            [kotoba.lang.text :as str]))

(def GRAPHS
  "name → delayed compiled langgraph-clj graph."
  {"health"        health/GRAPH
   "compose_tweet" compose-tweet/GRAPH
   "agent_chat"    agent-chat/GRAPH})

(def NSID->ASSISTANT
  {"com.etzhayyim.apps.x.health"       "health"
   "com.etzhayyim.apps.x.composeTweet" "compose_tweet"
   "com.etzhayyim.apps.x.chat"         "agent_chat"
   "com.etzhayyim.apps.x.agentChat"    "agent_chat"})

(defn camel->snake
  "elonMusk → elon_musk (mirrors server.py `_camel_to_snake`)."
  [s]
  (let [s (str s)]
    (apply str
           (map-indexed
            (fn [i ch]
              (if (and (pos? i) (Character/isUpperCase ^char ch))
                (str "_" (Character/toLowerCase ^char ch))
                (str (Character/toLowerCase ^char ch))))
            s))))

(defn- snake->kw
  "JSON/snake_case key → the kebab-case keyword the graph nodes read."
  [k]
  (keyword (str/replace (camel->snake (name k)) "_" "-")))

(defn xrpc-input->graph-input
  "Translate an XRPC body (camelCase keys) into graph input (kebab keywords).
  Mirrors `_xrpc_input_to_graph_input` ∘ `_camel_to_snake`."
  [body]
  (reduce-kv (fn [m k v] (assoc m (snake->kw k) v)) {}
             (or body {})))

(defn- graph-of [assistant-id]
  (when-let [d (get GRAPHS assistant-id)] @d))

(defn run
  "Invoke a graph by assistant-id with `input` (a clj map). Mirrors POST /runs.
  Returns {:ok true :result <state> :assistantId .. :latencyMs ..} or
          {:ok false :error .. :errorType .. :assistantId .. :latencyMs ..}."
  ([assistant-id input] (run assistant-id input {}))
  ([assistant-id input run-opts]
   (let [started (System/nanoTime)
         latency #(int (/ (- (System/nanoTime) started) 1000000))
         host-config (:host-config run-opts)
         input (cond-> (or input {}) host-config (assoc :host-config host-config))
         graph-opts (dissoc run-opts :host-config)]
     (if-not (contains? GRAPHS assistant-id)
       {:ok false :error (str "unknown graph: " assistant-id) :status 404}
       (try
         {:ok true :result (g/invoke (graph-of assistant-id) input graph-opts)
          :assistantId assistant-id :latencyMs (latency)}
         (catch Exception exc
           {:ok false :error (subs (str (.getMessage exc)) 0 (min 500 (count (str (.getMessage exc)))))
            :errorType (.. exc getClass getSimpleName)
            :assistantId assistant-id :latencyMs (latency)}))))))

(defn xrpc
  "Dispatch an XRPC call by NSID. Mirrors POST /xrpc/{nsid}: translate body, invoke
  the mapped graph, append latencyMs + assistantId. Returns the graph result map,
  or {:status 404/503} for unknown / unloaded."
  ([nsid body] (xrpc nsid body {}))
  ([nsid body {:keys [host-config]}]
  (let [assistant-id (get NSID->ASSISTANT nsid)]
    (cond
      (nil? assistant-id) {:status 404 :error (str "unknown NSID: " nsid)}
      (not (contains? GRAPHS assistant-id)) {:status 503 :error (str "graph not loaded: " assistant-id)}
      :else
      (let [started (System/nanoTime)
            latency #(int (/ (- (System/nanoTime) started) 1000000))
            input (cond-> (xrpc-input->graph-input body)
                    host-config (assoc :host-config host-config))]
        (try
          (let [result (g/invoke (graph-of assistant-id) input)]
            (assoc (if (map? result) result {:result result})
                   :latencyMs (latency) :assistantId assistant-id))
          (catch Exception exc
            {:error (str "lg-x " (.. exc getClass getSimpleName))
             :errorDetail (subs (str (.getMessage exc)) 0 (min 300 (count (str (.getMessage exc)))))
             :assistantId assistant-id :latencyMs (latency)})))))))

(defn ok
  "Mirrors GET /ok."
  []
  {:ok true :graphs (vec (keys GRAPHS)) :version "0.1.0"})
