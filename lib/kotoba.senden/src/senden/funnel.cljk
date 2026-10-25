(ns senden.funnel
  "Marketing funnel stages + conversion (pure). Stages:
  :awareness → :interest → :consideration → :purchase → :retention.
  A Funnel is {stage → count}. Conversion rate = next/prev."
  (:refer-clojure :exclude [empty])
  (:require [chobo.ledger :as ledger]))

(def stages [:awareness :interest :consideration :purchase :retention])

(defn stage-index [stage]
  (loop [i 0 [s & r] stages]
    (cond (nil? s) nil (= s stage) i :else (recur (inc i) r))))

(defrecord Funnel [counts])

(defn funnel [] (->Funnel (zipmap stages (repeat 0))))

(defn set-stage [f stage n] (assoc-in f [:counts stage] (max 0 n)))
(defn add-to-stage [f stage n] (update-in f [:counts stage] (fnil + 0) (max 0 n)))

(defn stage-count [f stage] (get-in f [:counts stage] 0))

(defn conversion-rate
  "Rate from stage → next stage (next/prev). 0 if prev is 0 or no next stage."
  [f stage]
  (let [i (stage-index stage)
        nxt (when i (nth stages (inc i) nil))]
    (if-not nxt
      0
      (let [prev-c (stage-count f stage)
            next-c (stage-count f nxt)]
        (if (pos? prev-c) (/ next-c prev-c) 0)))))

(defn overall-conversion-rate
  "End-to-end: retention / awareness."
  [f]
  (let [a (stage-count f :awareness)
        r (stage-count f :retention)]
    (if (pos? a) (/ r a) 0)))

;; ---------------------------------------------------------------------------
;; cohort retention (track a cohort's size over time periods)
;; ---------------------------------------------------------------------------

(defrecord Cohort [id period0-size retention])

(defn cohort [m] (merge {:retention []} m))

(defn retention-rate
  "Retention rate at period n = retention[n] / period0-size. Returns 0 if n is
  out of range or period0-size is 0."
  [c n]
  (let [p0 (:period0-size c 0)
        r (get-in c [:retention n] 0)]
    (if (pos? p0) (/ r p0) 0)))

(defn churn-rate
  "Churn rate at period n = 1 - retention-rate. Returns 0 for period 0."
  [c n]
  (if (zero? n)
    0
    (- 1 (retention-rate c n))))

(defn cumulative-churn
  "Total churn from period 0 to n = (period0 - retention[n]) / period0."
  [c n]
  (let [p0 (:period0-size c 0)
        r (get-in c [:retention n] 0)]
    (if (pos? p0) (/ (- p0 r) p0) 0)))

(defn lifetime-value-estimate
  "Rough LTV estimate: average-revenue-per-period / cumulative-churn-rate.
  Returns nil if churn is 0 (no churn = infinite LTV, uncomputable)."
  [c avg-revenue-per-period n]
  (let [cc (cumulative-churn c n)]
    (when (pos? cc)
      (/ avg-revenue-per-period cc))))

(defn cohort-activity
  "Build a ledger activity for a cohort retention event (lane :marketing,
  kind :cohort-retention)."
  [c n opts]
  (ledger/activity
   (merge {:lane :marketing :kind :cohort-retention
           :title (str "Cohort " (:id c "unknown") " period " n)
           :props {:cohort-id (:id c)
                   :period n
                   :retention-rate (retention-rate c n)
                   :churn-rate (churn-rate c n)}}
          opts)))
