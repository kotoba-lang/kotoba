(ns browser.compat.quickjs-binding
  "Host binding contract for a QuickJS WASM component."
  (:require [browser.compat.quickjs :as quickjs]
            [browser.event-loop :as event-loop]))

(defn empty-binding
  [adapter]
  {:quickjs/adapter adapter
   :quickjs/event-loop (event-loop/empty-loop)
   :quickjs/modules {}
   :quickjs/requests []
   :quickjs/results []})

(defn evaluate!
  [binding script]
  (let [req (quickjs/evaluate-request (:quickjs/adapter binding) script)]
    (update binding :quickjs/requests conj req)))

(defn module-load!
  [binding specifier referrer]
  (let [req (quickjs/module-load-request (:quickjs/adapter binding) specifier referrer)]
    (update binding :quickjs/requests conj req)))

(defn schedule-timeout!
  [binding callback-id delay-ms payload]
  (update binding :quickjs/event-loop event-loop/set-timeout callback-id delay-ms payload))

(defn cancel-timeout!
  [binding callback-id]
  (update binding :quickjs/event-loop event-loop/clear-timeout callback-id))

(defn queue-microtask!
  [binding callback-id payload]
  (update binding :quickjs/event-loop event-loop/queue-microtask callback-id payload))

(defn drain-jobs!
  [binding now-ms]
  (let [advanced (update binding :quickjs/event-loop event-loop/advance now-ms)
        {:keys [loop tasks]} (event-loop/drain (:quickjs/event-loop advanced))
        calls (mapv (fn [task]
                      (quickjs/job-drain-request (:quickjs/adapter binding)))
                    tasks)]
    (-> advanced
        (assoc :quickjs/event-loop loop)
        (update :quickjs/requests into calls)
        (update :quickjs/results conj {:job-drain/tasks tasks}))))
