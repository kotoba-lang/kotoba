(ns kotoba.pkg
  "KAMI Packaging — IC package modeling, wire bond / flip chip bonding, and
  thermal analysis. Pure data, no network/IO in any domain namespace.

  A kotoba-lang capability library. Ported from kami-pkg (Rust); see
  kotoba.pkg.bonding, kotoba.pkg.package, kotoba.pkg.thermal, and the
  swappable kotoba.pkg.registry config. This facade namespace mirrors the
  original crate's lib.rs re-exports (`pub use bonding::{..}; pub use
  package::{..}; pub use thermal::{..};`)."
  (:require [kotoba.pkg.bonding :as bonding]
            [kotoba.pkg.package :as package]
            [kotoba.pkg.registry :as registry]
            [kotoba.pkg.thermal :as thermal]))

;; ---------------------------------------------------------------------------
;; bonding
;; ---------------------------------------------------------------------------

(def wire-bond bonding/wire-bond)
(def flip-chip bonding/flip-chip)
(def thermo-compression bonding/thermo-compression)
(def pad-location bonding/pad-location)
(def bond bonding/bond)
(def generate-bond-diagram bonding/generate-bond-diagram)

;; ---------------------------------------------------------------------------
;; package
;; ---------------------------------------------------------------------------

(def qfp package/qfp)
(def bga package/bga)
(def csp package/csp)
(def wlcsp package/wlcsp)
(def sip package/sip)
(def chiplet-2-5d package/chiplet-2-5d)
(def chiplet-3d package/chiplet-3d)
(def estimate-package package/estimate-package)

;; ---------------------------------------------------------------------------
;; thermal
;; ---------------------------------------------------------------------------

(def thermal-spec thermal/thermal-spec)
(def calculate-thermal thermal/calculate-thermal)

;; ---------------------------------------------------------------------------
;; registry (config)
;; ---------------------------------------------------------------------------

(def default-registry registry/registry)
