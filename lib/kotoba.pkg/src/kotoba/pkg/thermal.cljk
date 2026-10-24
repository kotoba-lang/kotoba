(ns kotoba.pkg.thermal
  "Thermal analysis for IC packages — pure, no IO.

  Ported from kami-pkg (Rust) src/thermal.rs. The forced-airflow reduction
  exponent is a registry constant (see kotoba.pkg.registry :airflow-model),
  not hardcoded."
  (:require [kotoba.pkg.registry :as registry]))

(defn- pow [base exp]
  #?(:clj (Math/pow base exp)
     :cljs (.pow js/Math base exp)))

(defn thermal-spec
  "Thermal specification inputs. power-w: total dissipation (W). ambient-c:
  ambient temperature (C). theta-jc: junction-to-case thermal resistance
  (C/W). theta-ca: case-to-ambient thermal resistance (C/W). airflow-m-per-s:
  airflow velocity in m/s, or nil for natural convection."
  [power-w ambient-c theta-jc theta-ca & {:keys [airflow-m-per-s]}]
  {:power-w power-w
   :ambient-c ambient-c
   :theta-jc theta-jc
   :theta-ca theta-ca
   :airflow-m-per-s airflow-m-per-s})

(defn calculate-thermal
  "Calculate junction and case temperatures from a thermal spec using the
  simple thermal resistance network:

    Tj = Ta + P * (theta_jc + theta_ca_effective)
    Tc = Ta + P * theta_ca_effective

  Forced airflow reduces theta_ca by an empirical factor:
    theta_ca_effective = theta_ca / (1 + airflow_m_per_s) ^ reduction-exponent

  `reg` defaults to kotoba.pkg.registry/registry; pass an override map with
  the same shape for a different empirical model."
  ([spec] (calculate-thermal spec registry/registry))
  ([{:keys [power-w ambient-c theta-jc theta-ca airflow-m-per-s]} reg]
   (let [exponent (get-in reg [:airflow-model :reduction-exponent])
         theta-ca-effective (if (and airflow-m-per-s (pos? airflow-m-per-s))
                               (/ theta-ca (pow (+ 1.0 airflow-m-per-s) exponent))
                               theta-ca)
         theta-ja (+ theta-jc theta-ca-effective)
         case-temp (+ ambient-c (* power-w theta-ca-effective))
         junction-temp (+ ambient-c (* power-w theta-ja))]
     {:junction-temp-c junction-temp
      :case-temp-c case-temp
      :power-w power-w
      :ambient-c ambient-c
      :theta-ja theta-ja})))
