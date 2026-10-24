(ns kotoba.pkg.package
  "IC package type definitions and geometry/thermal estimation — pure, no IO.

  Ported from kami-pkg (Rust) src/package.rs. Geometry and thermal-model
  constants are not hardcoded here; they come from a registry map (see
  kotoba.pkg.registry), which defaults to kotoba.pkg.registry/registry but
  can be overridden per call for a different process/technology profile."
  (:require [kotoba.pkg.registry :as registry]))

;; ---------------------------------------------------------------------------
;; Package type constructors
;; ---------------------------------------------------------------------------

(defn qfp
  "Quad Flat Package."
  [pin-count pitch-mm]
  {:pkg-type/kind :qfp :pin-count pin-count :pitch-mm pitch-mm})

(defn bga
  "Ball Grid Array."
  [rows cols pitch-mm]
  {:pkg-type/kind :bga :rows rows :cols cols :pitch-mm pitch-mm})

(defn csp
  "Chip Scale Package."
  [rows cols pitch-mm]
  {:pkg-type/kind :csp :rows rows :cols cols :pitch-mm pitch-mm})

(defn wlcsp
  "Wafer Level Chip Scale Package."
  [bump-rows bump-cols bump-pitch-um]
  {:pkg-type/kind :wlcsp
   :bump-rows bump-rows
   :bump-cols bump-cols
   :bump-pitch-um bump-pitch-um})

(def sip
  "System in Package."
  {:pkg-type/kind :sip})

(def chiplet-2-5d
  "2.5D chiplet with silicon interposer."
  {:pkg-type/kind :chiplet-2-5d})

(def chiplet-3d
  "3D stacked chiplet."
  {:pkg-type/kind :chiplet-3d})

;; ---------------------------------------------------------------------------
;; Estimation
;; ---------------------------------------------------------------------------

(defn- geometry
  "Body dimensions (mm) and pin count for pkg-type, die-x/die-y (mm), given
  registry `reg`."
  [pkg-type die-x die-y reg]
  (case (:pkg-type/kind pkg-type)
    :qfp
    (let [{:keys [pin-count pitch-mm]} pkg-type
          side-pins (quot pin-count 4)
          clearance (get-in reg [:qfp :body-clearance-mm])
          z (get-in reg [:qfp :body-z-mm])
          body-side (+ (* side-pins pitch-mm) clearance)]
      {:pin-count pin-count :body-x body-side :body-y body-side :body-z z})

    :bga
    (let [{:keys [rows cols pitch-mm]} pkg-type
          clearance (get-in reg [:bga :body-clearance-mm])
          z (get-in reg [:bga :body-z-mm])]
      {:pin-count (* rows cols)
       :body-x (+ (* cols pitch-mm) clearance)
       :body-y (+ (* rows pitch-mm) clearance)
       :body-z z})

    :csp
    (let [{:keys [rows cols pitch-mm]} pkg-type
          clearance (get-in reg [:csp :body-clearance-mm])
          z (get-in reg [:csp :body-z-mm])]
      {:pin-count (* rows cols)
       :body-x (+ (* cols pitch-mm) clearance)
       :body-y (+ (* rows pitch-mm) clearance)
       :body-z z})

    :wlcsp
    (let [{:keys [bump-rows bump-cols bump-pitch-um]} pkg-type
          z (get-in reg [:wlcsp :body-z-mm])
          pitch-mm (/ bump-pitch-um 1000.0)]
      {:pin-count (* bump-rows bump-cols)
       :body-x (+ die-x pitch-mm)
       :body-y (+ die-y pitch-mm)
       :body-z z})

    :sip
    (let [{:keys [die-multiplier-x die-multiplier-y body-z-mm fixed-pin-count]} (:sip reg)]
      {:pin-count fixed-pin-count
       :body-x (* die-x die-multiplier-x)
       :body-y (* die-y die-multiplier-y)
       :body-z body-z-mm})

    :chiplet-2-5d
    (let [{:keys [die-multiplier-x die-multiplier-y body-z-mm fixed-pin-count]} (:chiplet-2-5d reg)]
      {:pin-count fixed-pin-count
       :body-x (* die-x die-multiplier-x)
       :body-y (* die-y die-multiplier-y)
       :body-z body-z-mm})

    :chiplet-3d
    (let [{:keys [die-multiplier-x die-multiplier-y body-z-mm fixed-pin-count]} (:chiplet-3d reg)]
      {:pin-count fixed-pin-count
       :body-x (* die-x die-multiplier-x)
       :body-y (* die-y die-multiplier-y)
       :body-z body-z-mm})))

(defn- package-name [pkg-type pin-count]
  (case (:pkg-type/kind pkg-type)
    :qfp (str "QFP-" pin-count)
    :bga (str "BGA-" pin-count)
    :csp (str "CSP-" pin-count)
    :wlcsp (str "WLCSP-" pin-count)
    :sip "SiP"
    :chiplet-2-5d "Chiplet-2.5D"
    :chiplet-3d "Chiplet-3D"))

(defn estimate-package
  "Estimate package body size and thermal properties from type and die size.

  Body dimensions include clearance around the die. Thermal resistances are
  estimated from package area using a simplified empirical model (see
  kotoba.pkg.registry :thermal-estimation). `die-size-mm` is [die-x die-y].
  `reg` defaults to kotoba.pkg.registry/registry; pass an override map with
  the same shape for a different process/technology profile."
  ([pkg-type die-size-mm] (estimate-package pkg-type die-size-mm registry/registry))
  ([pkg-type [die-x die-y :as die-size-mm] reg]
   (let [{:keys [pin-count body-x body-y body-z]} (geometry pkg-type die-x die-y reg)
         area (* body-x body-y)
         {:keys [base-theta-jc area-coeff-jc area-coeff-ca]} (:thermal-estimation reg)
         theta-jc (+ base-theta-jc (/ area-coeff-jc area))
         theta-ja (+ theta-jc (/ area-coeff-ca area))]
     {:name (package-name pkg-type pin-count)
      :pkg-type pkg-type
      :body-size-mm [body-x body-y body-z]
      :die-size-mm die-size-mm
      :pin-count pin-count
      :thermal-resistance-jc theta-jc
      :thermal-resistance-ja theta-ja})))
