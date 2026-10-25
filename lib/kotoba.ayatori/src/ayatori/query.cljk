(ns ayatori.query
  "Ayatori's public query plane.

  Ayatori weaves content-addressed graph data into queryable projections:
  IPLD owns values, links, traversal and verification; IPNI discovers
  providers for CIDs; CARv2 says where inside an object a block begins; this
  namespace owns the query-facing materialization and access paths.

  Discovery is deliberately absent from THIS namespace, and that is a
  boundary rather than a gap: finding a provider and evaluating a query are
  separate effects, and keeping them in separate namespaces is what stops an
  indexer response from being read as content. The wiring that does connect
  them -- discover, fetch, rehash, cursor, query -- is `ayatori.remote`, and
  the packed-block source it can read through is `ayatori.pack`.

  The implementation currently delegates to the compatibility namespace
  `kotobase.query.bridge`, so existing callers can migrate without changing
  semantics. `arrangement.datalog` remains the Datalog evaluator."
  (:refer-clojure :exclude [memo])
  (:require [kotobase.query.bridge :as legacy]))

(def entity-id legacy/entity-id)
(def default-max-datoms legacy/default-max-datoms)
(def materialize legacy/materialize)
(def default-memo-capacity legacy/default-memo-capacity)
(def memo legacy/memo)
(def materialize-memo legacy/materialize-memo)
(def memo-stats legacy/memo-stats)
(def db-for legacy/db-for)
(def entity-attrs legacy/entity-attrs)
(def by-predicate legacy/by-predicate)
(def by-predicate-value legacy/by-predicate-value)
(def refs-to legacy/refs-to)
(def datoms legacy/datoms)
(def q legacy/q)
(def query legacy/query)
