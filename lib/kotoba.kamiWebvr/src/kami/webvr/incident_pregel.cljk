(ns kami.webvr.incident-pregel
  "The choice-scenario state machine (ported from kami-engine-sdk's
   src/lib/webvr/incident-pregel.ts). Pure, deterministic, no I/O -- runs
   identically on the JVM and in ClojureScript.

   The original TS file also defines a compiled LangGraph `StateGraph`
   (`INCIDENT_GRAPH`, 8 super-steps s1..s8) that mirrors this logic node-by-
   node, for parity with LangGraph Studio tooling. This port deliberately
   does NOT reimplement that graph: per the original source's own research
   notes, `INCIDENT_GRAPH` is referenced but never `.invoke()`d by the real
   engine (`createIncidentVrEngine.svelte.ts` calls `applySelection`/
   `initialState` directly), and nothing in `webvr.test.ts` exercises the
   graph either -- it was non-functional documentation scaffolding. If a
   LangGraph-Studio-visualizable version is ever needed, it can be added
   later as a thin wrapper around these same pure functions without changing
   their semantics."
  (:require [kami.webvr.types :as t]))

(defn- node [scenario id]
  (or (get-in scenario [:nodes id])
      (throw (ex-info (str "kami.webvr: unknown node \"" id "\"") {:node-id id}))))

(defn- find-choice [n choice-id]
  (or (first (filter #(= choice-id (:id %)) (:choices n)))
      (throw (ex-info (str "kami.webvr: choice id \"" choice-id "\" not offered at node \""
                           (:id n) "\" (available: "
                           (pr-str (mapv :id (:choices n))) ")")
                       {:node-id (:id n) :choice-id choice-id}))))

(defn- now-iso []
  #?(:clj (str (java.time.Instant/now))
     :cljs (.toISOString (js/Date.))))

(defn initial-state
  "scenario -> the IncidentState at the scenario's start node."
  [scenario]
  {:current (:start scenario) :kpi t/zero-kpi :history [] :done false})

(defn apply-selection
  "scenario, state, choice-id -> the next IncidentState.
   Identity-preserving no-op if `state` is already :done (returns the same
   value, not a copy -- callers may rely on `=`/reference-equality checks).
   Throws if the current node or the chosen choice-id doesn't exist."
  [scenario state choice-id]
  (if (:done state)
    state
    (let [n (node scenario (:current state))]
      (if (:terminal n)
        (assoc state :done true :outcome (:terminal n))
        (let [choice (find-choice n choice-id)
              kpi (t/apply-kpi-delta (:kpi state) (:delta choice))
              decision {:node-id (:id n) :choice-id (:id choice) :taken-at (now-iso)
                        :kpi-after kpi :grade (:grade choice)}
              next-node (or (get-in scenario [:nodes (:next choice)])
                            (throw (ex-info (str "choice \"" (:id choice)
                                                 "\" points at unknown node \"" (:next choice) "\"")
                                            {:choice-id (:id choice) :next (:next choice)})))]
          {:current (:next choice)
           :kpi kpi
           :history (conj (:history state) decision)
           :done (boolean (:terminal next-node))
           :outcome (:terminal next-node)})))))

;; SceneDescriptor: {:location :camera-hint :choices :briefing :severity :stage
;;                    :terminal :cine :cine-panel :effects :node-id}
;;   :choices is a vector of {:id :label :hint}
;; IncidentBridge: {:on-scene (fn [scene]) :on-choice (fn [decision])
;;                  :on-terminal (fn [state])
;;                  :on-oplog (fn [{:op :node-id :choice-id :kpi :at}])}
;;   :op is one of #{:enter :choose :terminate}
