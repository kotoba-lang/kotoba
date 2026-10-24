(ns session.ports)

(defprotocol ISessionStore
  (put-session! [store session])
  (get-session [store session-id])
  (put-event! [store event])
  (events-for [store session-id]))

(defprotocol ISessionIndex
  (sessions-for-subject [store subject]))

(defn memory-session-store
  []
  (let [sessions (atom {})
        events (atom {})]
    (reify ISessionStore
      (put-session! [_ session]
        (swap! sessions assoc (:session/id session) session)
        session)
      (get-session [_ session-id]
        (get @sessions session-id))
      (put-event! [_ event]
        (swap! events update (:session.event/session-id event) (fnil conj []) event)
        event)
      (events-for [_ session-id]
        (get @events session-id []))
      ISessionIndex
      (sessions-for-subject [_ subject]
        (->> (vals @sessions)
             (filter #(= subject (:session/subject %)))
             vec)))))
