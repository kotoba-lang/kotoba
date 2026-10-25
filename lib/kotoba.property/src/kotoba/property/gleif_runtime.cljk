(ns kotoba.property.gleif-runtime
  (:require [kotoba.lang.text :as str]))

(def source-id "gleif-level-2")
(def api-root "https://api.gleif.org/api/v1/lei-records")

(declare normalize-entity-with-source)

(defn normalize-relation [observed-at relationship-data]
  (let [attributes (:attributes relationship-data)
        relation (:relationship attributes)]
    {:corporate-relation/id (:id relationship-data)
     :corporate-relation/child-lei (get-in relation [:startNode :id])
     :corporate-relation/parent-lei (get-in relation [:endNode :id])
     :corporate-relation/type (-> (get-in relation [:type])
                                  str/lower
                                  (str/replace "_" "-")
                                  keyword)
     :corporate-relation/status (-> (get-in relation [:status]) str/lower keyword)
     :corporate-relation/source source-id
     :corporate-relation/observed-at observed-at}))

(defn normalize-entity [observed-at entity-data]
  (normalize-entity-with-source source-id observed-at entity-data))

(defn normalize-entity-with-source [source observed-at entity-data]
  {:legal-entity/id (:id entity-data)
   :legal-entity/lei (get-in entity-data [:attributes :lei])
   :legal-entity/name (get-in entity-data [:attributes :entity :legalName :name])
   :legal-entity/registered-as (get-in entity-data [:attributes :entity :registeredAs])
   :legal-entity/jurisdiction (get-in entity-data [:attributes :entity :jurisdiction])
   :legal-entity/source source
   :legal-entity/observed-at observed-at})
