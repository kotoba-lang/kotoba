(ns onetime.ports)

(defprotocol IOneTime
  (verify! [port challenge response]))

(defprotocol IAttemptStore
  (consume-challenge! [store challenge-id]
    "Atomically consume a one-time challenge. Return true only the first time.")
  (record-attempt! [store challenge-id ok?]
    "Record one attempt and return the attempt count."))

(defprotocol IAttemptLookup
  (attempt-count [store challenge-id]))

(defn memory-attempt-store
  []
  (let [used (atom #{})
        attempts (atom {})]
    (reify IAttemptStore
      (consume-challenge! [_ challenge-id]
        (let [accepted? (atom false)]
          (swap! used
                 (fn [s]
                   (if (contains? s challenge-id)
                     s
                     (do (reset! accepted? true)
                         (conj s challenge-id)))))
          @accepted?))
      (record-attempt! [_ challenge-id _ok?]
        (get (swap! attempts update challenge-id (fnil inc 0)) challenge-id))
      IAttemptLookup
      (attempt-count [_ challenge-id]
        (get @attempts challenge-id 0)))))
