(ns kiyaku.return-analytics
  "Return reason categorization + analytics (pure). Aggregates return requests
  by reason, computes return rate (returns / orders), and identifies top reasons."
  (:require [kotoba.lang.text :as str]))

(def reason-categories
  "Map of specific reason → category for rollup."
  {:wrong-size     :sizing
   :too-small      :sizing
   :too-large      :sizing
   :defect         :quality
   :damaged        :quality
   :not-as-described :expectation
   :changed-mind   :preference
   :better-price   :preference
   :late-delivery  :logistics
   :other          :other})

(defn categorize-reason
  "Map a specific return reason to its category."
  [reason]
  (get reason-categories reason :other))

(defn aggregate-by-reason
  "Group return requests by :reason, returning {reason → count}."
  [returns]
  (reduce (fn [acc r]
            (let [reason (:reason r :other)]
              (update acc reason (fnil inc 0))))
          {} returns))

(defn aggregate-by-category
  "Group returns by their reason category, returning {category → count}."
  [returns]
  (reduce (fn [acc r]
            (let [cat (categorize-reason (:reason r :other))]
              (update acc cat (fnil inc 0))))
          {} returns))

(defn top-reasons
  "Return the top N reasons by count, as [{:reason :count} …]."
  ([returns]
   (top-reasons returns 5))
  ([returns n]
   (->> (aggregate-by-reason returns)
        (sort-by second >)
        (take n)
        (map (fn [[reason count]] {:reason reason :count count})))))

(defn return-rate
  "Return rate = total returned items / total order items. Returns a fraction
  (0.0–1.0). Caller passes total-order-items."
  [returns total-order-items]
  (if (pos? total-order-items)
    (/ (reduce + 0 (map #(reduce + 0 (map :qty (:items % []))) returns))
       total-order-items)
    0))

(defn reason-breakdown-activity
  "Build a reason-breakdown summary map for ledger projection (caller appends)."
  [returns]
  {:total (count returns)
   :by-reason (aggregate-by-reason returns)
   :by-category (aggregate-by-category returns)
   :top-reasons (top-reasons returns 3)})
