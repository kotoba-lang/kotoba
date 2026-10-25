(ns kotoba.plm.db
  "Domain-facing data facade — a thin delegation over the `Store` protocol
   (kotoba.plm.store). The whole domain (item / cost / thread / mrp /
   production) touches the graph only through these fns, so a connection can
   be a Datomic Local store (dev/test, kotoba.plm.store-datomic) or the
   kotoba-datomic XRPC store (prod) interchangeably.

   The 'db handle' returned by `db` IS the store: queries run against current
   state, so re-read `(db conn)` after each `tx!` rather than holding a snapshot."
  (:require [kotoba.plm.store :as store]))

(defn tx!   [conn tx]          (store/transact! conn tx))
(defn db    [conn]             conn)        ; store is the current-state handle
(defn q     [query conn & in]  (store/q* conn query in))   ; query-first (Datomic d/q order)
(defn pull  [conn pattern eid] (store/pull* conn pattern eid))
(defn attr  [conn a eid]       (store/attr conn a eid))
(defn exists? [conn eid]       (some? (:db/id (store/pull* conn [:db/id] eid))))
