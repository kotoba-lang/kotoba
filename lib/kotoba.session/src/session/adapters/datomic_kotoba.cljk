(ns session.adapters.datomic-kotoba
  (:require [session.datom :as datom]
            [session.ports :as p]))

(defprotocol IDatomicKotoba
  (transact! [conn tx-data opts])
  (pull-session [conn session-id opts])
  (events-by-session [conn session-id opts])
  (sessions-by-subject [conn subject opts]))

(defn- public-session [entity]
  (some-> entity (dissoc :db/id)))

(defn- public-event [entity]
  (some-> entity (dissoc :db/id :session.event/id)))

(defn datomic-kotoba-session-store
  ([conn] (datomic-kotoba-session-store conn {}))
  ([conn opts]
   (reify p/ISessionStore
     (put-session! [_ session]
       (transact! conn (datom/session-datoms session) opts)
       session)
     (get-session [_ session-id]
       (public-session (pull-session conn session-id opts)))
     (put-event! [_ event]
       (transact! conn (datom/event-datoms event) opts)
       event)
     (events-for [_ session-id]
       (mapv public-event (events-by-session conn session-id opts)))
     p/ISessionIndex
     (sessions-for-subject [_ subject]
       (mapv public-session (sessions-by-subject conn subject opts))))))

(defn memory-datomic-kotoba
  ([] (memory-datomic-kotoba (atom {:sessions {}
                                    :events {}
                                    :txs []})))
  ([state]
   (letfn [(record-tx! [tx-data opts]
             (swap! state update :txs conj {:tx-data tx-data
                                            :opts opts})
             {:tx-data tx-data})
           (store-entity! [entity]
             (cond
               (:session/id entity)
               (swap! state assoc-in [:sessions (:session/id entity)] entity)

               (:session.event/session-id entity)
               (swap! state update-in [:events (:session.event/session-id entity)]
                      (fnil conj []) entity)

               :else
               (throw (ex-info "unsupported Datomic/Kotoba entity" {:entity entity}))))]
     (reify
       IDatomicKotoba
       (transact! [_ tx-data opts]
         (doseq [entity tx-data]
           (store-entity! entity))
         (record-tx! tx-data opts))
       (pull-session [_ session-id _opts]
         (get-in @state [:sessions session-id]))
       (events-by-session [_ session-id _opts]
         (get-in @state [:events session-id] []))
       (sessions-by-subject [_ subject _opts]
         (->> (vals (:sessions @state))
              (filter #(= subject (:session/subject %)))
              vec))))))
