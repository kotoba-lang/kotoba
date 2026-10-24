(ns kotoba.fleet.view
  "Fold the whole fleet into one view: who holds what, what is pending, what has
  been decided. This is what a murakumo-style fleet operator renders across the
  2-PC / ~20-agent lattice."
  (:require [kotoba.fleet.governor :as gov]
            [kotoba.fleet.lease :as lease]
            [kotoba.fleet.store :as store]))

(defn- works
  "Distinct work-units mentioned by any lease or proposal."
  [db]
  (->> (store/datoms db)
       (keep (fn [[_ a v]] (when (#{:lease/work :proposal/work} a) v)))
       distinct
       sort))

(defn snapshot
  "A fleet snapshot at `now`: per-work holders, pending proposals, receipts."
  [db now]
  (let [ws (works db)]
    {:now     now
     :works   (mapv (fn [w]
                      {:work    w
                       :holder  (lease/holder db w now)
                       :leases  (count (lease/active-leases db w now))})
                    ws)
     :pending (count (gov/pending-proposals db))
     :datoms  (count (store/datoms db))}))
