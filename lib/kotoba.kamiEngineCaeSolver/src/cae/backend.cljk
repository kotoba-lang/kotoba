(ns cae.backend
  "High-fidelity adapter between the shared Kotoba contract and CAE dispatch."
  (:require [cae.solver :as cae]
            [kotoba.physics.contract :as contract]))

(def backend-id :kotoba/cae)

(defn- result-qualification [raw]
  (merge {:execution :qualified :numerical-verification :not-qualified
          :experimental-validation :not-qualified :industrial-release :not-qualified}
         (when (map? (:qualification raw)) (:qualification raw))))

(defrecord CaeBackend []
  contract/PhysicsBackend
  (descriptor [_] {:id backend-id :version 1 :fidelity :high-fidelity
                   :units contract/si-units
                   :capabilities #{:cfd :fem :process :materials :electromagnetics
                                   :production-simulation :external-solver :evidence}})
  (step [_ _ _]
    (throw (ex-info "CAE backend is a finite solver, not a realtime frame integrator"
                    {:backend backend-id})))
  (solve [_ case]
    (let [solver-case (get-in case [:case/controls :solver-case])]
      (when-not (and (= :high-fidelity (:case/fidelity case)) (map? solver-case)
                     (keyword? (get-in solver-case [:solver :kind])))
        (throw (ex-info "CAE case requires an explicit nested solver-case" {:case case})))
      (try
        (let [raw (cae/solve solver-case)]
          (contract/make-result
           {:case-id (:case/id case) :backend backend-id :status :completed
            :fields (if (map? raw) (dissoc raw :qualification :evidence) {:value raw})
            :qualification (result-qualification raw) :evidence (or (:evidence raw) [])}))
        (catch #?(:clj Exception :cljs :default) error
          (contract/make-result
           {:case-id (:case/id case) :backend backend-id :status :failed
            :fields {:error #?(:clj (.getMessage error) :cljs (.-message error))}
            :qualification {:execution :rejected :industrial-release :not-qualified}
            :evidence []}))))))

(def backend (->CaeBackend))
