(ns authorization.schema
  "The canonical schema for everything this library persists, written once in
  Datomic's installation tx-data dialect.

  A real Datomic connection transacts these forms as-is;
  `langchain.db/schema-from-tx-data` converts them to the DataScript-style map
  the in-memory store reads. Neither host restates the attributes in its own
  dialect.

  Identity attributes are declared unique so an entity keeps its identity
  across transactions. `:db/id` alone never did that: a string `:db/id` is a
  *tempid*, scoped to one transaction, so a request and the decision answering
  it only looked like one entity because both were written under the same
  string in the same write. They are two entities joined by a reference, which
  is what `:authz.decision/request` now says out loud."
  (:require [langchain.db :as db]))

(def authz
  "Authorization requests and the decisions issued against them.

  Nested EDN -- a request's context, a decision's effect trace and its
  obligations -- is stored as a `pr-str` string blob, the shape this
  workspace's other datom corpora use, because no Datomic value type holds a
  vector of maps. `authorization.datom/read-blobs` reads them back."
  [{:db/ident :authz.request/id :db/valueType :db.type/string
    :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :authz.request/principal :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :authz.request/action :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :authz.request/resource :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :authz.request/context :db/valueType :db.type/string :db/cardinality :db.cardinality/one
    :db/doc "EDN blob: the attributes a policy evaluates beyond principal/action/resource."}
   {:db/ident :authz.request/capability-ref :db/valueType :db.type/string :db/cardinality :db.cardinality/one}

   {:db/ident :authz.decision/request-id :db/valueType :db.type/string
    :db/cardinality :db.cardinality/one :db/unique :db.unique/identity
    :db/doc "The request this decision answers, and the identity of the decision itself -- one decision per request is the replay invariant."}
   {:db/ident :authz.decision/request :db/valueType :db.type/ref :db/cardinality :db.cardinality/one
    :db/doc "The request entity, so a decision can be read together with what was asked."}
   {:db/ident :authz.decision/decision :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :authz.decision/by :db/valueType :db.type/string :db/cardinality :db.cardinality/one
    :db/doc "The engine that decided."}
   {:db/ident :authz.decision/reason :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :authz.decision/policy-ref :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :authz.decision/policy-version :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :authz.decision/effect-trace :db/valueType :db.type/string :db/cardinality :db.cardinality/one
    :db/doc "EDN blob: the rules that matched, in evaluation order -- one blob rather than cardinality-many, because the order is part of the evidence."}
   {:db/ident :authz.decision/obligations :db/valueType :db.type/string :db/cardinality :db.cardinality/one
    :db/doc "EDN blob: what the caller must do for the decision to hold."}
   {:db/ident :authz.decision/issued-at :db/valueType :db.type/string :db/cardinality :db.cardinality/one}])

(def tx-data
  "Everything, for a host installing the whole schema at once."
  authz)

(def map-schema
  "`tx-data` in the map dialect `langchain.db` reads."
  (db/schema-from-tx-data tx-data))
