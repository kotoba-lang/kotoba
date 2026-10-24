(ns kotoba.captcha.audit)

(def sensitive-key-pattern
  #"(?i)(client.?key|api.?key|authorization|cookie|password|secret|token|solution|credential)")

(defn sensitive-key? [k]
  (boolean (re-find sensitive-key-pattern (name k))))

(defn redact
  "Recursively removes credentials and challenge solutions before audit storage."
  [value]
  (cond
    (map? value) (into {} (map (fn [[k v]] [k (if (sensitive-key? k) "[REDACTED]" (redact v))])) value)
    (vector? value) (mapv redact value)
    (set? value) (set (map redact value))
    (sequential? value) (mapv redact value)
    :else value))

(defprotocol AuditSink
  (append-event! [sink event])
  (events [sink task-id])
  (purge-before! [sink cutoff-ms]))

(defrecord MemoryAuditSink [state retention-ms clock]
  AuditSink
  (append-event! [_ event]
    (let [timestamp (or (:audit/at event) (clock))
          safe-event (-> event redact (assoc :audit/at timestamp))]
      (swap! state conj safe-event)
      safe-event))
  (events [_ task-id]
    (filterv #(or (nil? task-id) (= task-id (:task/id %))) @state))
  (purge-before! [_ cutoff-ms]
    (let [effective-cutoff (max cutoff-ms (- (clock) retention-ms))]
      (swap! state #(filterv (fn [event] (>= (:audit/at event) effective-cutoff)) %))
      (count @state))))

(defn memory-audit
  ([] (memory-audit {}))
  ([{:keys [retention-ms clock]
     :or {retention-ms (* 7 24 60 60 1000)
          clock #?(:clj #(System/currentTimeMillis) :cljs #(.now js/Date))}}]
   (->MemoryAuditSink (atom []) retention-ms clock)))
