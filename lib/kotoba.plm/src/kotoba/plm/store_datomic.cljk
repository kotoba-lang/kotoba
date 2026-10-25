(ns kotoba.plm.store-datomic
  "Datomic Local backend for kotoba.plm.store — dev/test only, opt-in via the
   :datomic (or :test) alias so the core library stays free of the
   com.datomic/local dependency."
  (:require [datomic.client.api :as d]
            [kotoba.plm.schema :as schema]
            [kotoba.plm.store :as store]))

(defrecord DatomicLocalStore [conn]
  store/Store
  (transact! [s tx] (d/transact conn {:tx-data (vec tx)}) s)
  (q*    [_ query inputs] (apply d/q query (d/db conn) inputs))
  (pull* [_ pattern eid]  (try (d/pull (d/db conn) pattern eid) (catch Exception _ nil))))

(defn datomic-local
  "Fresh in-memory Datomic Local store with the schema installed."
  ([] (datomic-local "kyber"))
  ([db-name]
   (let [client (d/client {:server-type :datomic-local :storage-dir :mem :system "kyber-plm"})]
     (d/delete-database client {:db-name db-name})
     (d/create-database client {:db-name db-name})
     (let [conn (d/connect client {:db-name db-name})]
       (d/transact conn {:tx-data schema/schema})
       (->DatomicLocalStore conn)))))
