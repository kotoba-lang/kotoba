(ns kotoba.fleet.core
  "Durable outer-loop wiring. One `tick!` = one bounded coordination round: the
  governor drains pending proposals (single git writer) and a fleet snapshot is
  produced. Long-running agents run their own coding loop OUTSIDE the tick;
  the tick is the auditable, crash-safe coordination heartbeat (lease TTLs make
  crashed agents' work reclaimable on the next round)."
  (:require [kotoba.fleet.governor :as gov]
            [kotoba.fleet.view :as view]))

(defn tick!
  "Run one coordination tick. Opts {:gate :materialize :now}. Returns
  {:receipts [...] :view {...}} — the receipts the governor wrote this round and
  the resulting fleet snapshot."
  [db {:keys [gate materialize now] :or {gate (constantly true)}}]
  (let [receipts (gov/drain! db {:gate gate :materialize materialize :now now})]
    {:receipts receipts
     :view     (view/snapshot db now)}))
