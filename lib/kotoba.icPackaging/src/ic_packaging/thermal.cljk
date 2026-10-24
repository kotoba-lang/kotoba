(ns ic-packaging.thermal
  "Thermal analysis for IC packages. Restored from kami-pkg's `thermal`
  module (deleted PR #82).")

(defn thermal-spec [power-w ambient-c theta-jc theta-ca airflow-m-per-s]
  {:power-w power-w :ambient-c ambient-c :theta-jc theta-jc :theta-ca theta-ca
   :airflow-m-per-s airflow-m-per-s})

(defn thermal-result [junction-temp-c case-temp-c power-w ambient-c theta-ja]
  {:junction-temp-c junction-temp-c :case-temp-c case-temp-c :power-w power-w
   :ambient-c ambient-c :theta-ja theta-ja})

(defn calculate-thermal
  "Calculate junction and case temperatures from `spec` using the simple
  thermal resistance network: `Tj = Ta + P*(theta_jc + theta_ca_eff)`,
  `Tc = Ta + P*theta_ca_eff`. Forced airflow reduces theta_ca by an
  empirical `1/sqrt(1+velocity)` factor."
  [spec]
  (let [{:keys [power-w ambient-c theta-jc theta-ca airflow-m-per-s]} spec
        theta-ca-effective (if (and airflow-m-per-s (pos? airflow-m-per-s))
                              (/ theta-ca (Math/sqrt (+ 1.0 airflow-m-per-s)))
                              theta-ca)
        theta-ja (+ theta-jc theta-ca-effective)
        case-temp (+ ambient-c (* power-w theta-ca-effective))
        junction-temp (+ ambient-c (* power-w theta-ja))]
    (thermal-result junction-temp case-temp power-w ambient-c theta-ja)))
