(ns vehicle.backend
  "Realtime soft-body backend for the shared Kotoba physics contract."
  (:require [kotoba.physics.contract :as contract] [kotoba.physics.vehicle :as shared]
            [vehicle.ground :as ground] [vehicle.models.garage :as garage]
            [vehicle.vehicle :as vehicle]))
(def backend-id :kotoba/kami-vehicle)
(defn instantiate-document [doc]
  (when-not (shared/document? doc) (throw (ex-info "invalid vehicle document" {:document doc})))
  (garage/build (or (:vehicle/preset doc) :sedan)))
(defn document-with-structure [doc state]
  (assoc doc :vehicle/structure {:nodes (:nodes state) :beams (:beams state)
                                 :triangles (:triangles state) :wheels (:wheels state)}))
(defrecord KamiVehicleBackend []
  contract/PhysicsBackend
  (descriptor [_] {:id backend-id :version 1 :fidelity :realtime :units contract/si-units
                   :document-kinds #{:vehicle}
                   :capabilities #{:vehicle-dynamics :soft-body :node-beam :plastic-deformation
                                   :beam-breakage :pacejka-tires :powertrain :multi-surface-ground}})
  (step [_ scene dt]
    (update scene :scene/entities
            (fn [entities]
              (mapv (fn [entity]
                      (if (= :vehicle (:entity/domain entity))
                        (let [state (or (:vehicle/state entity)
                                        (instantiate-document (:vehicle/document entity)))
                              state (assoc state :controls (merge (:controls state) (:vehicle/controls entity)))
                              grnd (or (:vehicle/ground entity) (ground/map-ground-demo-circuit))
                              next-state (vehicle/step state dt grnd)]
                          (assoc entity :vehicle/state next-state
                                 :vehicle/document (document-with-structure (:vehicle/document entity) next-state)))
                        entity)) entities))))
  (solve [_ _] (throw (ex-info "realtime backend does not finite-solve" {:backend backend-id}))))
(def backend (->KamiVehicleBackend))
