(ns lg.lg-kyber.graphs.health
  "kyber `health` graph — minimal liveness probe. Faithful langgraph-clj port of
  graphs/health.py: a one-node StateGraph (START → probe → END) that compiles and
  actually invokes under bb (no host gate needed — it only reads the clock + an env)."
  (:require [langgraph.graph :as g]))

(def version-key ::version)

(defn probe
  "Port of _probe — {ok ts version}. ts = epoch-ms; version from LG_KYBER_VERSION."
  [state]
  {"ok"      true
   "ts"      #?(:clj (System/currentTimeMillis) :default 0)
   "version" (or (get state version-key) "0.0.1")})

(defn build
  "Compile the health StateGraph (START → probe → END)."
  []
  (-> (g/state-graph)
      (g/add-node :probe probe)
      (g/set-entry-point :probe)
      (g/set-finish-point :probe)
      (g/compile-graph)))

(def graph (build))

(defn run [input] (g/invoke graph input))
