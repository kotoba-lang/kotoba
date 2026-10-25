(ns datomic.client.api
  "Drop-in namespace shim for the published Datomic Client API shape.

  The implementation is `kotobase.datomic.client`. This namespace intentionally
  matches the public var names so an application can change only its dependency,
  not every call site. It does not implement Cognitect's proprietary Cloud wire
  protocol and must not be placed on a classpath together with com.datomic/client."
  (:refer-clojure :exclude [sync])
  (:require [kotobase.datomic.client :as impl]))

(def administer-system impl/administer-system)
(def as-of impl/as-of)
(def client impl/client)
(def connect impl/connect)
(def create-database impl/create-database)
(def datoms impl/datoms)
(def db impl/db)
(def db-stats impl/db-stats)
(def delete-database impl/delete-database)
(def history impl/history)
(def index-pull impl/index-pull)
(def index-range impl/index-range)
(def list-databases impl/list-databases)
(def pull impl/pull)
(def q impl/q)
(def qseq impl/qseq)
(def rseek-datoms impl/rseek-datoms)
(def seek-datoms impl/seek-datoms)
(def since impl/since)
(def sync impl/sync)
(def transact impl/transact)
(def tx-range impl/tx-range)
(def with impl/with)
(def with-db impl/with-db)
