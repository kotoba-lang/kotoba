(ns kotoba.plm.routing
  "BOP (Bill of Process) — routing master data: work centers and the ordered
   operations an item's own build performs on them. Pure constructors (tx
   maps) + queries; no ERP side effects live here (kotoba.plm.cost /
   kotoba.plm.production read this to fold process cost into the standard-cost
   roll-up and backflush, ADR-2607141000)."
  (:require [kotoba.plm.db :as db]
            [kotoba.plm.erp :as erp]))

(defn work-center
  "Build a work-center tx map. `rate` is currency per hour (labor + overhead
   absorption)."
  [{:keys [id name rate] :or {rate 0}}]
  {:plm.wc/id   id
   :plm.wc/name (or name id)
   :plm.wc/rate (erp/->bigdec rate)})

(defn operation
  "Build a routing-step tx map for `item` (\"<part>@<rev>\") at `seq`, run on
   `work-center` (a :plm.wc/id). `setup-time-hr` is charged in full per unit
   (no lot-size amortization in this cut — pre-divide by an assumed lot size
   before calling if lot averaging is wanted)."
  [{:keys [item seq name work-center std-time-hr setup-time-hr]
    :or   {std-time-hr 0 setup-time-hr 0}}]
  {:plm.op/id            (str item "|" seq)
   :plm.op/item          [:plm.item/id item]
   :plm.op/seq           (long seq)
   :plm.op/name          (or name (str "op-" seq))
   :plm.op/work-center   [:plm.wc/id work-center]
   :plm.op/std-time-hr   (erp/->bigdec std-time-hr)
   :plm.op/setup-time-hr (erp/->bigdec setup-time-hr)})

(defn routing-for-item
  "Routing steps of `iid` as
   [{:seq :name :work-center :std-time-hr :setup-time-hr :rate} ...],
   ordered by seq."
  [d iid]
  (->> (db/q '[:find ?seq ?name ?wcid ?std ?setup ?rate
               :in $ ?iid
               :where
               [?i :plm.item/id ?iid]
               [?o :plm.op/item ?i]
               [?o :plm.op/seq ?seq]
               [?o :plm.op/name ?name]
               [?o :plm.op/work-center ?wc]
               [?wc :plm.wc/id ?wcid]
               [?wc :plm.wc/rate ?rate]
               [?o :plm.op/std-time-hr ?std]
               [?o :plm.op/setup-time-hr ?setup]]
             d iid)
       (map (fn [[seq name wcid std setup rate]]
              {:seq seq :name name :work-center wcid
               :std-time-hr std :setup-time-hr setup :rate rate}))
       (sort-by :seq)
       vec))

(defn process-cost
  "Standard process cost of one unit of `iid`'s OWN routing
   (Σ (std-time + setup-time) × work-center rate). Does not recurse into
   children — kotoba.plm.cost/rolled-cost adds this per level as it walks
   the MBOM, so children's own process cost is picked up independently."
  [d iid]
  (reduce (fn [acc {:keys [std-time-hr setup-time-hr rate]}]
            (+ acc (* (+ std-time-hr setup-time-hr) rate)))
          0M
          (routing-for-item d iid)))
