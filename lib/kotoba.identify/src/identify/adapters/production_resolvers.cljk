(ns identify.adapters.production-resolvers
  (:require [kotoba.lang.text :as str]
            [identify.model :as m]
            [identify.ports :as p]))

(defprotocol IResolver
  (resolve! [resolver identifier opts]))

(defn normalize-identifier [identifier]
  (let [type (:identify.identifier/type identifier)
        value (:identify.identifier/value identifier)]
    (assoc identifier :identify.identifier/value
           (case type
             :email (some-> value str/lower str/trim)
             :wallet (some-> value str/lower)
             :did (some-> value str/trim)
             :device (some-> value str)
             value))))

(defn- ->candidate [response]
  (m/candidate (:subject response) (:confidence response)
               {:evidence-ref (:evidence-ref response)
                :evidence-refs (:evidence-refs response)
                :asserter (:asserter response)
                :source (:source response)
                :assertions (:assertions response)
                :conflict? (:conflict? response)}))

(defn production-resolver-port
  ([routes] (production-resolver-port routes {}))
  ([routes opts]
   (reify p/IIdentify
     (resolve-candidates [_ identifier]
       (let [identifier (normalize-identifier identifier)
             resolver (get routes (:identify.identifier/type identifier))]
         (when-not resolver
           (throw (ex-info "resolver not configured"
                           {:identify.identifier/type (:identify.identifier/type identifier)})))
         (mapv ->candidate (resolve! resolver identifier opts)))))))

(defn static-resolver [responses]
  (reify IResolver
    (resolve! [_ _identifier _opts] responses)))
