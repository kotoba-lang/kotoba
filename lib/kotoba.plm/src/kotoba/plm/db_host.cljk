(ns kotoba.plm.db-host
  "JVM host provider for the optional Datomic Local development backend.

  Portable domain code depends only on kotoba.plm.db and Store. Namespace
  loading and JVM backend selection happen statically at this host boundary."
  (:require [kotoba.plm.store-datomic :as datomic]))

(defn fresh-conn
  "Create a Datomic Local store with the PLM schema installed."
  ([] (fresh-conn "kyber"))
  ([db-name] (datomic/datomic-local db-name)))
