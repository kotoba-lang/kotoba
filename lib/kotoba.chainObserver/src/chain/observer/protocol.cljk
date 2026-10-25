(ns chain.observer.protocol
  "Transport-neutral, read-only chain observation contracts.")

(defprotocol Adapter
  (request-plan [adapter]
    "Finite allowlisted read-only requests required for one snapshot.")
  (normalize [adapter responses]
    "Normalize role-keyed responses into a validated snapshot."))

(defprotocol ChainObserver
  (snapshot [observer]
    "Execute one observation and return a validated immutable snapshot."))

(defrecord PlannedObserver [adapter request-fn]
  ChainObserver
  (snapshot [_]
    (let [responses
          (reduce
           (fn [result {:keys [role] :as request}]
             (let [resolved
                   (update (dissoc request :role) :params
                           (fn [params]
                             (mapv #(if (and (keyword? %)
                                             (= "chain.observer"
                                                (namespace %)))
                                      (get result
                                           (keyword (name %)))
                                      %)
                                   params)))]
               (assoc result role (request-fn resolved))))
           {}
           (request-plan adapter))]
      (normalize adapter responses))))

(defn observer [adapter request-fn]
  (when-not (ifn? request-fn)
    (throw (ex-info "Chain observer requires an injected request function."
                    {:type :chain.observer/invalid-transport})))
  (->PlannedObserver adapter request-fn))
