(ns identify.adapters.resolver
  (:require [identify.model :as m]
            [identify.ports :as p]))

(defprotocol IResolverClient
  (resolve-identifier! [client payload opts]))

(defn- payload [identifier]
  {:type (:identify.identifier/type identifier)
   :value (:identify.identifier/value identifier)
   :source (:identify.identifier/source identifier)
   :observed-at (:identify.identifier/observed-at identifier)})

(defn- candidate [response]
  (m/candidate (:subject response)
               (:confidence response)
               {:evidence-ref (:evidence-ref response)
                :asserter (:asserter response)
                :source (:source response)}))

(defn resolver-port [client opts]
  (reify p/IIdentify
    (resolve-candidates [_ identifier]
      (mapv candidate (resolve-identifier! client (payload identifier) opts)))))
