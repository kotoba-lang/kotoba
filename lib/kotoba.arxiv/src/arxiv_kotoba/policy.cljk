(ns arxiv-kotoba.policy)

(def risk-rank
  {:read-only 0
   :external-auth 1
   :external-draft 2
   :public-submit 3
   :destructive 4})

(def default-autonomy
  {:read-only :auto
   :external-auth :approve
   :external-draft :approve
   :public-submit :approve
   :destructive :approve})

(defn risk-of
  [capability]
  (or (:risk capability) :destructive))

(defn approval-required?
  ([capability] (approval-required? default-autonomy capability))
  ([autonomy capability]
   (let [autonomy (or autonomy default-autonomy)
         risk (risk-of capability)]
     (or (contains? (set (:requires capability)) :human-approval)
         (not= :auto (get autonomy risk :approve))))))

(defn allowed?
  [{:keys [approved? autonomy]} capability]
  (or (not (approval-required? autonomy capability))
      (true? approved?)))
