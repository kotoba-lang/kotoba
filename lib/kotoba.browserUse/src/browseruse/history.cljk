(ns browseruse.history)

(defrecord ActionResult [step action input output error url attempts elapsed-ms metadata])
(defrecord AgentHistory [session-id settings actions metadata])

(defn empty-history
  ([session-id] (empty-history session-id nil))
  ([session-id settings] (->AgentHistory session-id settings [] {})))

(defn append [history result] (update history :actions conj result))
(defn export [history] (into {} history))

(defn replay
  "Replay exported history through an injected `(fn [action-result])`. No
  browser driver is assumed, so callers may audit without side effects."
  [history execute!]
  (mapv execute! (:actions history)))

