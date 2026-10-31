(ns kotoba.biomech.softbody
  "Soft biological tissue (muscle, skin, organ wall) — thin wrapper on
  vehicle.softbody, the vehicle-agnostic mass-spring-damper core now living
  in kotoba-lang/kami-vehicle (Phase 2.1: the integrator was promoted out of
  this namespace, which used to re-implement it). This namespace keeps the
  biomech-specific tissue -> spring/damping parameter mapping and re-exports
  the generic soft-body API."
  (:require [vehicle.softbody :as sb]
            [kotoba.biomech.tissue :as tissue]))

;; Re-export the generic soft-body API (now in vehicle.softbody).
(def make-grid  sb/make-grid)
(def anchor-row sb/anchor-row)
(def fixed?     sb/fixed?)
(def step       sb/step)
(def simulate   sb/simulate)

(defn tissue->spring-params
  "Map a biomech tissue to a representative [spring damping] pair
  ([N/m, N·s/m]) for a soft-body grid. Soft tissues span ~1-100 kPa; these
  are order-of-magnitude teaching defaults, not patient-specific."
  [t]
  (case (tissue/tissue-type t)
    :muscle [200.0  5.0]
    :skin   [50.0   3.0]
    :organ  [30.0   4.0]
    :tendon [5000.0 20.0]
    [100.0  5.0]))
