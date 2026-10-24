(ns kotoba.captcha.worker-store
  (:require [kotoba.captcha.domain :as domain]
            [kotoba.captcha.store :as store]))

(defprotocol WorkerStore
  (claim-next! [queue worker-id lease-ms now-ms])
  (renew-lease! [queue task-id lease-token lease-ms now-ms])
  (complete-task! [queue task-id lease-token solution now-ms])
  (retry-task! [queue task-id lease-token error next-at now-ms])
  (fail-task! [queue task-id lease-token error now-ms])
  (cancel-task! [queue task-id reason now-ms]))

(defn- claimable? [task now-ms]
  (and (<= (or (:task/next-at task) 0) now-ms)
       (or (= :queued (:task/status task))
           (and (= :processing (:task/status task))
                (<= (or (:task/lease-until task) 0) now-ms)))))

(defn- owns-lease? [task lease-token now-ms]
  (and (= :processing (:task/status task))
       (= lease-token (:task/lease-token task))
       (> (or (:task/lease-until task) 0) now-ms)))

(defrecord TaskStoreWorkerAdapter [task-store token-generator]
  WorkerStore
  (claim-next! [_ worker-id lease-ms now-ms]
    (when-let [candidate (->> (store/list-tasks task-store)
                              (filter #(claimable? % now-ms))
                              (sort-by (juxt #(or (:task/next-at %) 0) :task/created-at))
                              first)]
      (let [token (token-generator)]
        (store/update-task!
         task-store (:task/id candidate)
         (fn [current]
           (if (claimable? current now-ms)
             (-> current
                 (assoc :task/status :processing
                        :task/worker-id worker-id
                        :task/lease-token token
                        :task/lease-until (+ now-ms lease-ms)
                        :task/updated-at now-ms)
                 (update :task/attempt (fnil inc 0)))
             current)))
        (let [claimed (store/get-task task-store (:task/id candidate))]
          (when (= token (:task/lease-token claimed)) claimed)))))
  (renew-lease! [_ task-id token lease-ms now-ms]
    (store/update-task! task-store task-id
                        #(if (owns-lease? % token now-ms)
                           (assoc % :task/lease-until (+ now-ms lease-ms) :task/updated-at now-ms)
                           %)))
  (complete-task! [_ task-id token solution now-ms]
    (store/update-task! task-store task-id
                        #(if (owns-lease? % token now-ms)
                           (domain/transition % :ready
                                              {:task/result solution
                                               :task/lease-token nil
                                               :task/lease-until nil}
                                              now-ms)
                           %)))
  (retry-task! [_ task-id token error next-at now-ms]
    (store/update-task! task-store task-id
                        #(if (owns-lease? % token now-ms)
                           (assoc % :task/error error :task/next-at next-at
                                  :task/lease-until now-ms :task/updated-at now-ms)
                           %)))
  (fail-task! [_ task-id token error now-ms]
    (store/update-task! task-store task-id
                        #(if (owns-lease? % token now-ms)
                           (domain/transition % :failed
                                              {:task/error error
                                               :task/lease-token nil
                                               :task/lease-until nil}
                                              now-ms)
                           %)))
  (cancel-task! [_ task-id reason now-ms]
    (store/update-task! task-store task-id
                        #(if (contains? #{:queued :processing} (:task/status %))
                           (domain/transition % :cancelled
                                              {:task/error reason
                                               :task/lease-token nil
                                               :task/lease-until nil}
                                              now-ms)
                           %))))

(defn task-store-adapter
  ([task-store] (task-store-adapter task-store domain/task-id))
  ([task-store token-generator] (->TaskStoreWorkerAdapter task-store token-generator)))
