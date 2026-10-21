(ns kotoba.scheduler.due-jobs
  "due-jobs -- addressed on its own.

  Split out of kotoba.lang.scheduler on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn due-jobs
  "Return the jobs whose :at <= now, sorted by :at then id."
  [sch now]
  (let [n (if (:time/instant now) (:time/instant now) (long now))]
    (->> (:jobs sch)
         (filter (fn [[_id job]] (<= (:time/instant (:at job)) n)))
         (sort-by (fn [[id job]] [(:time/instant (:at job)) (name id)])))))
