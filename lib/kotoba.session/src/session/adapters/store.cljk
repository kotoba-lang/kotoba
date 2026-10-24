(ns session.adapters.store
  (:require [session.ports :as p]))

(defprotocol IKeyValueStore
  (put! [store key value opts])
  (get! [store key opts])
  (append! [store key value opts]))

(defn- session-key [session-id]
  (str "session:" session-id))

(defn- event-key [session-id]
  (str "session-events:" session-id))

(defn- subject-key [subject]
  (str "session-subject:" subject))

(defn kv-session-store [kv opts]
  (reify p/ISessionStore
    (put-session! [_ session]
      (put! kv (session-key (:session/id session)) session opts)
      (append! kv (subject-key (:session/subject session)) (:session/id session) opts)
      session)
    (get-session [_ session-id]
      (get! kv (session-key session-id) opts))
    (put-event! [_ event]
      (append! kv (event-key (:session.event/session-id event)) event opts)
      event)
    (events-for [_ session-id]
      (or (get! kv (event-key session-id) opts) []))
    p/ISessionIndex
    (sessions-for-subject [_ subject]
      (->> (or (get! kv (subject-key subject) opts) [])
           distinct
           (keep #(get! kv (session-key %) opts))
           vec))))
