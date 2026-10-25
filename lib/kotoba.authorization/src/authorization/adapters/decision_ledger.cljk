(ns authorization.adapters.decision-ledger
  "The port a host implements to make authorization decisions durable.
  `authorization.adapters.journal-ledger` is the implementation this repo
  ships; a host with its own transactor implements the same one method."
  (:require [authorization.datom :as datom]))

(defprotocol IDecisionLedger
  (transact! [ledger datoms opts]))

(defn persist-request!
  ([ledger request] (persist-request! ledger request {}))
  ([ledger request opts]
   (transact! ledger (datom/request-datoms request) opts)))

(defn persist-decision!
  "Persists a decision together with the request it answers, as one
  transaction -- the unit `authorization.datom/decision-tx` defines, and the
  unit `:authz.decision/request` needs in order to resolve."
  ([ledger request decision] (persist-decision! ledger request decision {}))
  ([ledger request decision opts]
   (transact! ledger (datom/decision-tx request decision) opts)))
