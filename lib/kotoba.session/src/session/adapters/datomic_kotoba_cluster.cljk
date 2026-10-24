(ns session.adapters.datomic-kotoba-cluster
  (:require [session.adapters.datomic-kotoba :as dk]))

(defprotocol IClusterAdmin
  (install-schema! [admin schema opts])
  (export-tx-audit! [admin opts]))

(def session-schema
  [{:db/ident :session/id :db/unique :db.unique/identity}
   {:db/ident :session/subject}
   {:db/ident :session/status}
   {:db/ident :session.event/id :db/unique :db.unique/identity}
   {:db/ident :session.event/session-id}
   {:db/ident :session.event/type}])

(defn bootstrap! [admin opts]
  (install-schema! admin session-schema opts))

(defn audit-export [admin opts]
  (export-tx-audit! admin opts))

(defn memory-cluster-admin
  ([] (memory-cluster-admin (atom {:schemas [] :audits []})))
  ([state]
   (reify IClusterAdmin
     (install-schema! [_ schema opts]
       (swap! state update :schemas conj {:schema schema :opts opts})
       {:installed? true :schema-count (count schema)})
     (export-tx-audit! [_ opts]
       (let [audit {:exported? true :opts opts}]
         (swap! state update :audits conj audit)
         audit))
     dk/IDatomicKotoba
     (transact! [_ tx-data opts]
       (swap! state update :txs conj {:tx-data tx-data :opts opts}))
     (pull-session [_ _session-id _opts] nil)
     (events-by-session [_ _session-id _opts] [])
     (sessions-by-subject [_ _subject _opts] []))))
