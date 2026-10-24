(ns vllm.scheduler
  "Bounded concurrent inference scheduler with per-model admission control."
  (:refer-clojure :exclude [run!])
  (:import [java.io Closeable]
           [java.util ArrayList]
           [java.util.concurrent ArrayBlockingQueue CompletableFuture ExecutionException
            LinkedBlockingQueue
            RejectedExecutionException Semaphore ThreadPoolExecutor
            ThreadPoolExecutor$AbortPolicy TimeUnit]
           [java.util.concurrent.atomic LongAdder]))

(defrecord Scheduler [^ThreadPoolExecutor executor model-permits max-per-model
                      batch-queues batch-running batch-window-ms max-batch-size queue-capacity
                      batch-history
                      ^LongAdder submitted ^LongAdder completed ^LongAdder failed
                      ^LongAdder rejected]
  Closeable
  (close [_]
    (.shutdown executor)
    (when-not (.awaitTermination executor 5 TimeUnit/SECONDS)
      (.shutdownNow executor))))

(defn scheduler
  [{:keys [workers queue-capacity max-per-model batch-window-ms max-batch-size]
    :or {workers (max 1 (.availableProcessors (Runtime/getRuntime)))
         queue-capacity 64 max-per-model 1 batch-window-ms 2 max-batch-size 16}}]
  (when-not (and (every? pos-int? [workers queue-capacity max-per-model max-batch-size])
                 (<= 0 batch-window-ms 1000))
    (throw (ex-info "scheduler capacities must be positive integers" {})))
  (->Scheduler
   (ThreadPoolExecutor. workers workers 0 TimeUnit/MILLISECONDS
                        (ArrayBlockingQueue. queue-capacity)
                        (ThreadPoolExecutor$AbortPolicy.))
   (atom {}) max-per-model (atom {}) (atom #{}) batch-window-ms max-batch-size queue-capacity
   (atom [])
   (LongAdder.) (LongAdder.) (LongAdder.) (LongAdder.)))

(defn- permit [scheduler model-name]
  (or (get @(:model-permits scheduler) model-name)
      (get (swap! (:model-permits scheduler)
                  #(if (contains? % model-name) %
                       (assoc % model-name (Semaphore. (:max-per-model scheduler) true))))
           model-name)))

(defn submit! [scheduler model-name thunk]
  (let [result (CompletableFuture.) p (permit scheduler model-name)
        task (reify Runnable
               (run [_]
                 (.acquire ^Semaphore p)
                 (try
                   (.complete result (thunk))
                   (.increment ^LongAdder (:completed scheduler))
                   (catch Throwable error
                     (.increment ^LongAdder (:failed scheduler))
                     (.completeExceptionally result error))
                   (finally (.release ^Semaphore p)))))]
    (try
      (.execute ^ThreadPoolExecutor (:executor scheduler) task)
      (.increment ^LongAdder (:submitted scheduler))
      result
      (catch RejectedExecutionException error
        (.increment ^LongAdder (:rejected scheduler))
        (throw (ex-info "inference queue is full" {:model model-name} error))))))

(defn run! [scheduler model-name thunk]
  (try (.get ^CompletableFuture (submit! scheduler model-name thunk))
       (catch ExecutionException error (throw (.getCause error)))))

(declare start-batch-dispatch!)

(defn- finish-batch! [scheduler requests batch-fn]
  (swap! (:batch-history scheduler)
         #(vec (take-last 64 (conj % (count requests)))))
  (try
    (let [results (vec (batch-fn (mapv :payload requests)))]
      (when-not (= (count results) (count requests))
        (throw (ex-info "batch executor returned wrong result count"
                        {:expected (count requests) :actual (count results)})))
      (doseq [[request result] (map vector requests results)]
        (.complete ^CompletableFuture (:future request) result)
        (.increment ^LongAdder (:completed scheduler))))
    (catch Throwable error
      (doseq [request requests]
        (.completeExceptionally ^CompletableFuture (:future request) error)
        (.increment ^LongAdder (:failed scheduler))))))

(defn- start-batch-dispatch! [scheduler model-name]
  (let [elected? (atom false)]
    (swap! (:batch-running scheduler)
           (fn [running]
             (if (contains? running model-name) running
               (do (reset! elected? true) (conj running model-name)))))
    (when @elected?
      (let [queue ^LinkedBlockingQueue (get @(:batch-queues scheduler) model-name)
            task
            (reify Runnable
              (run [_]
                (try
                  (loop []
                    (when-let [first-request (.poll queue)]
                      (when (pos? (:batch-window-ms scheduler))
                        (Thread/sleep (long (:batch-window-ms scheduler))))
                      (let [more (ArrayList.)
                            _ (.drainTo queue more (dec (:max-batch-size scheduler)))
                            requests (into [first-request] more)]
                        (finish-batch! scheduler requests (:batch-fn first-request))
                        (recur))))
                  (finally
                    (swap! (:batch-running scheduler) disj model-name)
                    (when-not (.isEmpty queue)
                      (start-batch-dispatch! scheduler model-name))))))]
        (try (.execute ^ThreadPoolExecutor (:executor scheduler) task)
             (catch RejectedExecutionException error
               (swap! (:batch-running scheduler) disj model-name)
               (throw (ex-info "inference queue is full" {:model model-name} error))))))))

(defn submit-batch!
  "Submit one payload to a continuously formed per-model cohort. `batch-fn`
  receives a vector of payloads and must return equally many ordered results."
  [scheduler model-name payload batch-fn]
  (let [queue (or (get @(:batch-queues scheduler) model-name)
                  (get (swap! (:batch-queues scheduler)
                              #(if (contains? % model-name) %
                                 (assoc % model-name
                                        (LinkedBlockingQueue.
                                         (int (:queue-capacity scheduler)))))) model-name))
        future (CompletableFuture.) request {:payload payload :future future :batch-fn batch-fn}]
    (if (.offer ^LinkedBlockingQueue queue request)
      (do (.increment ^LongAdder (:submitted scheduler))
          (start-batch-dispatch! scheduler model-name) future)
      (do (.increment ^LongAdder (:rejected scheduler))
          (throw (ex-info "inference queue is full" {:model model-name}))))))

(defn run-batch! [scheduler model-name payload batch-fn]
  (try (.get ^CompletableFuture (submit-batch! scheduler model-name payload batch-fn))
       (catch ExecutionException error (throw (.getCause error)))))

(defn stats [scheduler]
  (let [executor ^ThreadPoolExecutor (:executor scheduler)]
    {:submitted (.sum ^LongAdder (:submitted scheduler))
     :completed (.sum ^LongAdder (:completed scheduler))
     :failed (.sum ^LongAdder (:failed scheduler))
     :rejected (.sum ^LongAdder (:rejected scheduler))
     :active (.getActiveCount executor)
     :queued (.size (.getQueue executor))
     :batch-queued (reduce + 0 (map #(.size ^LinkedBlockingQueue %)
                                    (vals @(:batch-queues scheduler))))
     :recent-batch-sizes @(:batch-history scheduler)
     :queue-remaining (.remainingCapacity (.getQueue executor))}))
