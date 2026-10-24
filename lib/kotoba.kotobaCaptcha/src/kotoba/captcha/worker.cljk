(ns kotoba.captcha.worker
  (:require [kotoba.captcha.audit :as audit]
            [kotoba.captcha.provider :as provider]
            [kotoba.captcha.worker-store :as worker-store]))

(def default-options
  {:lease-ms 30000 :timeout-ms 20000 :max-attempts 3
   :base-retry-ms 500 :max-retry-ms 30000})

(defn- power-of-two [exponent]
  (loop [n exponent result 1]
    (if (zero? n) result (recur (dec n) (* 2 result)))))

(defn retry-delay-ms [{:keys [base-retry-ms max-retry-ms]} attempt]
  (min max-retry-ms (* base-retry-ms (power-of-two (max 0 (dec attempt))))))

(defn- emit! [sink task kind attrs now]
  (when sink
    (audit/append-event! sink (merge {:audit/event kind :task/id (:task/id task)
                                      :task/type (:task/type task) :audit/at now}
                                     attrs))))

(defn- invoke-provider [selected task context timeout-ms]
  #?(:clj
     (let [operation (future
                       (try (provider/solve! selected task context)
                            (catch Throwable error
                              {:status :retry :error (ex-message error)})))
           result (deref operation timeout-ms ::timeout)]
       (when (= ::timeout result) (future-cancel operation))
       (if (= ::timeout result)
         {:status :retry :error "Provider deadline exceeded"}
         result))
     :cljs
     (let [_ timeout-ms]
       (try (provider/solve! selected task context)
            (catch :default error
              {:status :retry :error (ex-message error)})))))

(defn- retry-or-fail! [queue task token result options finished]
  (let [attempt (:task/attempt task)]
    (if (>= attempt (:max-attempts options))
      (worker-store/fail-task! queue (:task/id task) token
                               (or (:error result) "Maximum attempts exceeded") finished)
      (let [delay (or (:retry-after-ms result) (retry-delay-ms options attempt))]
        (worker-store/retry-task! queue (:task/id task) token
                                  (or (:error result) (name (:status result)))
                                  (+ finished delay) finished)))))

(defn run-once!
  "Claims and executes at most one task. Timeout is a bounded result deadline;
  hosts requiring hard preemption should isolate providers in a process."
  [{:keys [queue providers audit worker-id clock] :as runtime}]
  (let [options (merge default-options (:options runtime))
        now (clock)]
    (when-let [task (worker-store/claim-next! queue worker-id (:lease-ms options) now)]
      (let [token (:task/lease-token task)
            selected (provider/select-provider providers task)
            started (clock)
            result (if selected
                     (invoke-provider selected task
                                      {:deadline-ms (+ started (:timeout-ms options))
                                       :worker-id worker-id}
                                      (:timeout-ms options))
                     {:status :failed :error "No provider supports this task type"})
            finished (clock)]
        (emit! audit task :worker/attempt
               {:provider/id (some-> selected provider/provider-id)
                :attempt (:task/attempt task) :result/status (:status result)} finished)
        (case (:status result)
          :ready (worker-store/complete-task! queue (:task/id task) token (:solution result) finished)
          :failed (worker-store/fail-task! queue (:task/id task) token (:error result) finished)
          :retry (retry-or-fail! queue task token result options finished)
          :waiting-human (retry-or-fail! queue task token result options finished)
          (worker-store/fail-task! queue (:task/id task) token "Invalid provider result" finished))
        result))))

(defn cancel! [{:keys [queue audit clock]} task-id reason]
  (let [now (clock)
        task (worker-store/cancel-task! queue task-id reason now)]
    (when task (emit! audit task :worker/cancelled {:reason reason} now))
    task))

(defn run-bounded!
  "Runs no more than max-tasks, stopping early when the queue has no claimable work."
  [runtime max-tasks]
  (loop [processed 0 results []]
    (if (>= processed max-tasks)
      results
      (if-let [result (run-once! runtime)]
        (recur (inc processed) (conj results result))
        results))))
