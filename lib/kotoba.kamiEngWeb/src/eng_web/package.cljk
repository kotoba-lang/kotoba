(ns eng-web.package
  "IC package-type parsing + preset config, restored from
  `kami-eng-web/src/lib.rs` (`pkg_estimate`/`pkg_thermal` wasm entry points),
  part of the legacy `kami-engine` Rust workspace deleted in
  kotoba-lang/kami-engine PR #82. See ADR-2607010930 (`com-junkawasaki/root`).

  Portable: the `pkg_type` string -> `kami_pkg::PackageType` preset-literal
  construction, and the fixed `ThermalSpec` defaults. Excluded: the actual
  `kami_pkg::package::estimate_package`/`kami_pkg::thermal::calculate_thermal`
  computations, which live in the unported `kami-pkg` crate."
  (:require [kotoba.lang.text :as str]))

(defn parse-package-type
  "Parse a package-type string (\"QFP\"/\"BGA\"/\"CSP\"/\"WLCSP\", case
  insensitive) into its preset config map, mirroring the literal preset
  values hard-coded in the original `pkg_estimate` wasm entry point.
  Returns nil for unknown package types."
  [pkg-type]
  (case (str/upper (str pkg-type))
    "QFP"   {:type :qfp :pin-count 144 :pitch-mm 0.5}
    "BGA"   {:type :bga :rows 20 :cols 20 :pitch-mm 0.8}
    "CSP"   {:type :csp :rows 10 :cols 10 :pitch-mm 0.5}
    "WLCSP" {:type :wlcsp :bump-rows 8 :bump-cols 8 :bump-pitch-um 400.0}
    nil))

(defn thermal-spec-defaults
  "Build the `ThermalSpec` input used by `pkg_thermal`: fixed
  `theta_jc`/`theta_ca` constants from the original Rust, with no airflow."
  [power-w ambient-c]
  {:power-w power-w
   :ambient-c ambient-c
   :theta-jc 5.0
   :theta-ca 20.0
   :airflow-m-per-s nil})
