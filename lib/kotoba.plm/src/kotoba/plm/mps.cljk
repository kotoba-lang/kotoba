(ns kotoba.plm.mps
  "MPS (Master Production Schedule) — time-phased top-level demand, item ×
   period bucket. Pure constructors + queries; kotoba.plm.mrp reads
   :approved lines as the demand source for plan-from-mps/mrp-run-from-mps!
   (ADR-2607141000). The existing explicit-demand kotoba.plm.mrp/plan and
   mrp-run! are unchanged — this is an additional demand source, not a
   replacement."
  (:require [kotoba.plm.db :as db]
            [kotoba.plm.erp :as erp]))

(defn mps-line
  "Build an MPS-line tx map. `period` is a java.util.Date bucket start.
   `kind` is :forecast (planning estimate) | :firm (candidate for approval).
   New lines always start :draft; approve by transacting
   {:plm.mps/id id :plm.mps/state :approved}."
  [{:keys [item period qty kind] :or {kind :forecast}}]
  {:plm.mps/id     (str item "|" (.getTime period))
   :plm.mps/item   [:plm.item/id item]
   :plm.mps/period period
   :plm.mps/qty    (erp/->bigdec qty)
   :plm.mps/kind   kind
   :plm.mps/state  :draft})

(defn mps-for-item
  "MPS lines for `iid` as [{:period :qty :kind :state} ...], sorted by period."
  [d iid]
  (->> (db/q '[:find ?period ?qty ?kind ?state
               :in $ ?iid
               :where
               [?i :plm.item/id ?iid]
               [?m :plm.mps/item ?i]
               [?m :plm.mps/period ?period]
               [?m :plm.mps/qty ?qty]
               [?m :plm.mps/kind ?kind]
               [?m :plm.mps/state ?state]]
             d iid)
       (map (fn [[period qty kind state]]
              {:period period :qty qty :kind kind :state state}))
       (sort-by :period)
       vec))

(defn approved-demand-for-item
  "Sum of :approved MPS qty for `iid` within [from to) (java.util.Date bounds,
   `to` exclusive). nil bounds ⇒ unbounded on that side."
  [d iid from to]
  (->> (mps-for-item d iid)
       (filter #(= :approved (:state %)))
       (filter (fn [{:keys [period]}]
                 (and (or (nil? from) (not (pos? (compare from period))))
                      (or (nil? to) (neg? (compare period to))))))
       (map :qty)
       (reduce + 0M)))
