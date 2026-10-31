(ns cae.industrial
  "Portable, deterministic engineering reference solvers.

  These are deliberately reduced-order solvers: they make an OpenUSD/CAD/BIM
  case useful before a dedicated CFD, FEM, electromagnetic, or manufacturing
  CAE adapter is selected.  All results retain SI units and use the common
  `cae.solver/solve` dispatch, so a host can replace any method without
  changing the case envelope."
  (:require [cae.solver :as cae]))

(def ^:private pi Math/PI)

(defn- finite-number? [x]
  (and (number? x)
       #?(:clj (Double/isFinite (double x))
          :cljs (js/isFinite x))))

(defn- positive! [input ks]
  (doseq [k ks]
    (when-not (and (finite-number? (get input k)) (pos? (double (get input k))))
      (throw (ex-info "industrial CAE input must be a finite positive number"
                      {:field k :value (get input k)})))))

(defn- nonnegative! [input ks]
  (doseq [k ks]
    (when-not (and (finite-number? (get input k)) (not (neg? (double (get input k)))))
      (throw (ex-info "industrial CAE input must be a finite non-negative number"
                      {:field k :value (get input k)})))))

(defn- unit-interval! [input ks]
  (doseq [k ks]
    (when-not (and (finite-number? (get input k))
                   (<= 0.0 (double (get input k)) 1.0))
      (throw (ex-info "industrial CAE input must be in [0, 1]"
                      {:field k :value (get input k)})))))

(defn- screening-result
  "Attach the common traceability envelope required for every reference result."
  [input kind model assumptions]
  (cond-> {:solver kind :model model :fidelity :reduced-order
           :status :screening-only :units :SI :assumptions assumptions}
    (:case/id input) (assoc :case/id (:case/id input))
    (:case/provenance input) (assoc :case/provenance (:case/provenance input))))

(defn cfd
  "Steady incompressible duct/ventilation model.
  Case keys: `:flow-m3-s :duct-diameter-m :duct-length-m`; optional
  `:rho-kg-m3 :viscosity-pa-s :roughness-m :minor-loss-coefficient`
  (sum of fittings/damper/filter K values), `:efficiency :heat-load-W`.
  Set all of `:fuel-mass-flow-kg-s :lower-heating-value-J-kg`
  `:combustion-efficiency` to include a steady combustion heat source.
  Returns pressure drop, Reynolds number, fan power and outlet temperature."
  [{:keys [flow-m3-s duct-diameter-m duct-length-m rho-kg-m3 viscosity-pa-s
           roughness-m minor-loss-coefficient efficiency heat-load-W inlet-temperature-C cp-J-kgK
           fuel-mass-flow-kg-s lower-heating-value-J-kg combustion-efficiency]
    :or {rho-kg-m3 1.204 viscosity-pa-s 1.825e-5 roughness-m 1.5e-5
         minor-loss-coefficient 0.0 efficiency 0.65 heat-load-W 0.0 inlet-temperature-C 20.0
         cp-J-kgK 1006.0}
    :as input}]
  (positive! input [:flow-m3-s :duct-diameter-m :duct-length-m])
  (positive! {:rho-kg-m3 rho-kg-m3 :viscosity-pa-s viscosity-pa-s
              :efficiency efficiency :cp-J-kgK cp-J-kgK}
             [:rho-kg-m3 :viscosity-pa-s :efficiency :cp-J-kgK])
  (nonnegative! {:roughness-m roughness-m :minor-loss-coefficient minor-loss-coefficient
                 :heat-load-W heat-load-W}
                [:roughness-m :minor-loss-coefficient :heat-load-W])
  (let [combustion-values [fuel-mass-flow-kg-s lower-heating-value-J-kg combustion-efficiency]
        combustion? (some some? combustion-values)]
    (when-not (apply = (map some? combustion-values))
      (throw (ex-info "combustion heat source requires fuel flow, heating value, and efficiency"
                      {:fuel-mass-flow-kg-s fuel-mass-flow-kg-s
                       :lower-heating-value-J-kg lower-heating-value-J-kg
                       :combustion-efficiency combustion-efficiency})))
    (when combustion?
      (positive! {:fuel-mass-flow-kg-s fuel-mass-flow-kg-s
                  :lower-heating-value-J-kg lower-heating-value-J-kg}
                 [:fuel-mass-flow-kg-s :lower-heating-value-J-kg])
      (unit-interval! {:combustion-efficiency combustion-efficiency} [:combustion-efficiency])
      (when (zero? (double combustion-efficiency))
        (throw (ex-info "combustion efficiency must be positive"
                        {:field :combustion-efficiency :value combustion-efficiency}))))
    (let [area (/ (* pi duct-diameter-m duct-diameter-m) 4.0)
        velocity (/ flow-m3-s area)
        re (/ (* rho-kg-m3 velocity duct-diameter-m) viscosity-pa-s)
        relative-roughness (/ roughness-m duct-diameter-m)
        ;; Laminar Hagen-Poiseuille; Swamee-Jain explicit turbulent correlation.
        friction (if (< re 2300.0)
                   (/ 64.0 re)
                   (/ 0.25 (Math/pow (Math/log10 (+ (/ relative-roughness 3.7)
                                                      (/ 5.74 (Math/pow re 0.9)))) 2.0)))
        dynamic-pressure (/ (* rho-kg-m3 velocity velocity) 2.0)
        major-dp (* friction (/ duct-length-m duct-diameter-m) dynamic-pressure)
        minor-dp (* minor-loss-coefficient dynamic-pressure)
        dp (+ major-dp minor-dp)
        mass-flow (* rho-kg-m3 flow-m3-s)
        combustion-heat-W (if combustion?
                            (* fuel-mass-flow-kg-s lower-heating-value-J-kg combustion-efficiency)
                            0.0)
        total-heat-load-W (+ heat-load-W combustion-heat-W)
        delta-t (/ total-heat-load-W (* mass-flow cp-J-kgK))]
      (merge (screening-result input :cfd :steady-duct-flow
                               (cond-> [:incompressible-fluid :fully-developed-flow :single-duct
                                        :Darcy-Weisbach-major-loss :lumped-minor-loss]
                                 combustion? (conj :steady-combustion-heat-source)))
           {:regime (if (< re 2300.0) :laminar :turbulent)
            :area-m2 area :velocity-m-s velocity :reynolds re
            :darcy-friction-factor friction :dynamic-pressure-Pa dynamic-pressure
            :major-pressure-drop-Pa major-dp :minor-pressure-drop-Pa minor-dp
            :pressure-drop-Pa dp
            :fan-power-W (/ (* dp flow-m3-s) efficiency)
            :process-heat-load-W heat-load-W :combustion-heat-W combustion-heat-W
            :total-heat-load-W total-heat-load-W
            :outlet-temperature-C (+ inlet-temperature-C delta-t)}))))

(defn fem
  "Linear structural screening with axial-bar and cantilever-beam elements.
  `:element` defaults to `:axial-bar` (`:area-m2`). `:cantilever-beam` uses a
  rectangular section (`:width-m`, `:height-m`) with a tip load. Both return
  static deformation/stress, first mode, and Basquin-fatigue estimates."
  [{:keys [element length-m area-m2 width-m height-m youngs-modulus-Pa load-N
           density-kg-m3 yield-strength-Pa stress-range-Pa basquin-b basquin-C]
    :or {element :axial-bar density-kg-m3 7850.0 yield-strength-Pa 355e6 stress-range-Pa 0.0
         basquin-b -0.12 basquin-C 1.0e11}
    :as input}]
  (positive! input [:length-m :youngs-modulus-Pa :load-N])
  (positive! {:density-kg-m3 density-kg-m3 :yield-strength-Pa yield-strength-Pa
              :basquin-C basquin-C}
             [:density-kg-m3 :yield-strength-Pa :basquin-C])
  (nonnegative! {:stress-range-Pa stress-range-Pa} [:stress-range-Pa])
  (when-not (and (finite-number? basquin-b) (neg? (double basquin-b)))
    (throw (ex-info "Basquin exponent must be finite and negative" {:field :basquin-b :value basquin-b})))
  (let [life (if (pos? stress-range-Pa)
               (Math/pow (/ stress-range-Pa basquin-C) (/ 1.0 basquin-b))
               ##Inf)]
    (case element
      :axial-bar
      (do
        (positive! input [:area-m2])
        (let [stiffness (/ (* youngs-modulus-Pa area-m2) length-m)
              displacement (/ load-N stiffness)
              stress (/ load-N area-m2)
              mass (* density-kg-m3 area-m2 length-m)
              ;; First fixed-free axial mode: f = (1/4L)*sqrt(E/rho).
              f1 (/ (Math/sqrt (/ youngs-modulus-Pa density-kg-m3)) (* 4.0 length-m))]
          (merge (screening-result input :fem :linear-axial-bar
                                   [:small-strain :linear-elastic :fixed-free-first-axial-mode])
                 {:element element :cross-sectional-area-m2 area-m2
                  :stiffness-N-m stiffness :displacement-m displacement :stress-Pa stress
                  :safety-factor (/ yield-strength-Pa stress) :mass-kg mass
                  :first-natural-frequency-Hz f1 :first-axial-frequency-Hz f1
                  :fatigue-life-cycles life})))

      :cantilever-beam
      (do
        (positive! input [:width-m :height-m])
        (let [area (* width-m height-m)
              ;; Rectangular second moment about the axis normal to height.
              second-moment (/ (* width-m height-m height-m height-m) 12.0)
              section-modulus (/ second-moment (/ height-m 2.0))
              stiffness (/ (* 3.0 youngs-modulus-Pa second-moment)
                           (* length-m length-m length-m))
              displacement (/ load-N stiffness)
              stress (/ (* load-N length-m) section-modulus)
              mass (* density-kg-m3 area length-m)
              ;; Euler-Bernoulli fixed-free first bending mode, beta_1 = 1.875104.
              beta1 1.875104
              f1 (/ (* beta1 beta1 (Math/sqrt (/ (* youngs-modulus-Pa second-moment)
                                                 (* density-kg-m3 area))))
                    (* 2.0 pi length-m length-m))]
          (merge (screening-result input :fem :linear-cantilever-beam
                                   [:small-deflection :Euler-Bernoulli :fixed-free-first-bending-mode])
                 {:element element :cross-sectional-area-m2 area
                  :second-moment-m4 second-moment :section-modulus-m3 section-modulus
                  :stiffness-N-m stiffness :displacement-m displacement :stress-Pa stress
                  :safety-factor (/ yield-strength-Pa stress) :mass-kg mass
                  :first-natural-frequency-Hz f1 :first-bending-frequency-Hz f1
                  :fatigue-life-cycles life})))

      (throw (ex-info "unknown FEM element" {:element element
                                               :supported [:axial-bar :cantilever-beam]})))))

(defn process
  "Manufacturing-process reference models. Set `:process` to `:weld`, `:cast`
  or `:roll`.  The result is intentionally a screening estimate, not a weld
  procedure qualification or a foundry/rolling-mill signoff."
  [{:keys [process voltage-V current-A travel-speed-mm-s efficiency
           mass-kg latent-heat-J-kg superheat-K cp-J-kgK
           initial-thickness-mm final-thickness-mm flow-stress-MPa width-m
           mold-constant-s-m-2 volume-m3 surface-area-m2]
    :or {efficiency 0.8 cp-J-kgK 600.0 latent-heat-J-kg 2.7e5 superheat-K 50.0
         flow-stress-MPa 180.0 width-m 1.0}
    :as input}]
  (case process
    :weld (do (positive! input [:voltage-V :current-A :travel-speed-mm-s])
              (unit-interval! {:efficiency efficiency} [:efficiency])
              (when (zero? (double efficiency))
                (throw (ex-info "welding efficiency must be positive" {:field :efficiency :value efficiency})))
              (let [heat-input (/ (* voltage-V current-A efficiency) travel-speed-mm-s)]
                (merge (screening-result input :process :weld-heat-input
                                         [:constant-arc-efficiency :steady-travel-speed])
                       {:process :weld :heat-input-J-mm heat-input
                        :line-energy-kJ-mm (/ heat-input 1000.0)})))
    :cast (do (positive! input [:mass-kg])
              (positive! {:latent-heat-J-kg latent-heat-J-kg :cp-J-kgK cp-J-kgK}
                         [:latent-heat-J-kg :cp-J-kgK])
              (nonnegative! {:superheat-K superheat-K} [:superheat-K])
              (let [geometry-values [mold-constant-s-m-2 volume-m3 surface-area-m2]
                    chvorinov? (some some? geometry-values)]
                (when-not (apply = (map some? geometry-values))
                  (throw (ex-info "Chvorinov solidification requires mold constant, volume, and surface area"
                                  {:mold-constant-s-m-2 mold-constant-s-m-2
                                   :volume-m3 volume-m3 :surface-area-m2 surface-area-m2})))
                (when chvorinov?
                  (positive! {:mold-constant-s-m-2 mold-constant-s-m-2
                              :volume-m3 volume-m3 :surface-area-m2 surface-area-m2}
                             [:mold-constant-s-m-2 :volume-m3 :surface-area-m2]))
                (let [energy (* mass-kg (+ latent-heat-J-kg (* cp-J-kgK superheat-K)))
                      solidification-time (when chvorinov?
                                             (* mold-constant-s-m-2
                                                (Math/pow (/ volume-m3 surface-area-m2) 2.0)))]
                (merge (screening-result input :process :casting-energy-balance
                                         (cond-> [:uniform-superheat :latent-heat-constant]
                                           chvorinov? (conj :Chvorinov-solidification)))
                       {:process :cast :solidification-energy-J energy
                        :specific-energy-J-kg (/ energy mass-kg)}
                       (when chvorinov? {:solidification-time-s solidification-time})))))
    :roll (do (positive! input [:initial-thickness-mm :final-thickness-mm])
              (positive! {:flow-stress-MPa flow-stress-MPa :width-m width-m}
                         [:flow-stress-MPa :width-m])
              (when-not (> initial-thickness-mm final-thickness-mm)
                (throw (ex-info "rolling requires initial thickness > final thickness"
                                {:initial initial-thickness-mm :final final-thickness-mm})))
              (let [reduction (/ (- initial-thickness-mm final-thickness-mm) initial-thickness-mm)
                    force (* flow-stress-MPa 1e6 width-m (/ (+ initial-thickness-mm final-thickness-mm) 2000.0))]
                (merge (screening-result input :process :rolling-mean-pressure
                                         [:constant-flow-stress :plane-strain-width])
                       {:process :roll :reduction reduction
                        :true-strain (Math/log (/ initial-thickness-mm final-thickness-mm))
                        :rolling-force-N force})))
    (throw (ex-info "unknown manufacturing process" {:process process}))))

(defn materials
  "JMAK isothermal transformation / material-property estimate.
  Case keys: `:temperature-K :time-s`; optional `:avrami-n :rate-constant-s-n`
  for constant-rate kinetics, or `:pre-exponential-s-n` plus
  `:activation-energy-J-mol` for Arrhenius kinetics, and baseline material
  properties."
  [{:keys [temperature-K time-s avrami-n rate-constant-s-n density-kg-m3
           youngs-modulus-Pa hardness-base-HV hardness-transformed-HV
           pre-exponential-s-n activation-energy-J-mol gas-constant-J-molK]
    :or {avrami-n 2.0 rate-constant-s-n 1.0e-6 density-kg-m3 7850.0
         youngs-modulus-Pa 210e9 hardness-base-HV 180.0 hardness-transformed-HV 420.0
         gas-constant-J-molK 8.314462618}
    :as input}]
  (positive! input [:temperature-K :time-s])
  (positive! {:avrami-n avrami-n
              :density-kg-m3 density-kg-m3 :youngs-modulus-Pa youngs-modulus-Pa}
             [:avrami-n :density-kg-m3 :youngs-modulus-Pa])
  (nonnegative! {:hardness-base-HV hardness-base-HV
                 :hardness-transformed-HV hardness-transformed-HV}
                [:hardness-base-HV :hardness-transformed-HV])
  (let [arrhenius? (or (some? pre-exponential-s-n) (some? activation-energy-J-mol))]
    (when (not= (some? pre-exponential-s-n) (some? activation-energy-J-mol))
      (throw (ex-info "Arrhenius kinetics requires both pre-exponential and activation energy"
                      {:pre-exponential-s-n pre-exponential-s-n
                       :activation-energy-J-mol activation-energy-J-mol})))
    (if arrhenius?
      (do (positive! {:pre-exponential-s-n pre-exponential-s-n
                      :gas-constant-J-molK gas-constant-J-molK}
                     [:pre-exponential-s-n :gas-constant-J-molK])
          (nonnegative! {:activation-energy-J-mol activation-energy-J-mol}
                        [:activation-energy-J-mol]))
      (positive! {:rate-constant-s-n rate-constant-s-n} [:rate-constant-s-n]))
    (let [rate (if arrhenius?
                 (* pre-exponential-s-n
                    (Math/exp (- (/ activation-energy-J-mol
                                    (* gas-constant-J-molK temperature-K)))))
                 rate-constant-s-n)
          fraction (- 1.0 (Math/exp (- (* rate (Math/pow time-s avrami-n)))))]
      (merge (screening-result input :materials :JMAK
                               (cond-> [:isothermal-hold :single-transformation-product]
                                 arrhenius? (conj :Arrhenius-rate-law)))
           {:temperature-K temperature-K :transformed-fraction fraction
            :kinetics (if arrhenius? :Arrhenius :constant-rate)
            :rate-constant-s-n rate
            :hardness-HV (+ hardness-base-HV (* fraction (- hardness-transformed-HV hardness-base-HV)))
            :density-kg-m3 density-kg-m3 :youngs-modulus-Pa youngs-modulus-Pa}))))

(defn emag
  "Electromagnetic motor or induction-heating screening model.
  `:mode` defaults to `:motor`: use `:line-voltage-V :current-A
  :power-factor :speed-rpm` and optional electrical/thermal loss values.
  `:induction-heating` uses `:heating-power-W :coupling-efficiency
  :thermal-mass-kg :specific-heat-J-kgK :duration-s` to calculate a lumped
  workpiece temperature rise."
  [{:keys [mode line-voltage-V current-A power-factor speed-rpm efficiency
           stator-resistance-ohm ambient-C thermal-resistance-K-W
           heating-power-W coupling-efficiency thermal-mass-kg specific-heat-J-kgK
           duration-s initial-temperature-C]
    :or {mode :motor efficiency 0.93 stator-resistance-ohm 0.02 ambient-C 25.0
         thermal-resistance-K-W 0.08}
    :as input}]
  (case mode
    :motor
    (do
      (positive! input [:line-voltage-V :current-A :power-factor :speed-rpm])
      (unit-interval! {:power-factor power-factor :efficiency efficiency} [:power-factor :efficiency])
      (positive! {:thermal-resistance-K-W thermal-resistance-K-W} [:thermal-resistance-K-W])
      (nonnegative! {:stator-resistance-ohm stator-resistance-ohm} [:stator-resistance-ohm])
      (let [pin (* (Math/sqrt 3.0) line-voltage-V current-A power-factor)
            pout (* pin efficiency)
            omega (* speed-rpm (/ (* 2.0 pi) 60.0))
            copper-loss (* 3.0 current-A current-A stator-resistance-ohm)
            total-loss (- pin pout)]
        (when (> copper-loss total-loss)
          (throw (ex-info "efficiency is inconsistent with the specified copper loss"
                          {:efficiency efficiency :copper-loss-W copper-loss :total-loss-W total-loss})))
        (merge (screening-result input :emag :balanced-three-phase-steady-state
                                 [:sinusoidal-balanced-supply :lumped-thermal-resistance])
               {:mode mode :input-power-W pin :output-power-W pout :torque-Nm (/ pout omega)
                :copper-loss-W copper-loss :other-loss-W (- total-loss copper-loss)
                :total-loss-W total-loss
                :winding-temperature-C (+ ambient-C (* thermal-resistance-K-W total-loss))
                :efficiency efficiency})))

    :induction-heating
    (do
      (positive! input [:heating-power-W :thermal-mass-kg :specific-heat-J-kgK :duration-s])
      (unit-interval! {:coupling-efficiency coupling-efficiency} [:coupling-efficiency])
      (when (zero? (double coupling-efficiency))
        (throw (ex-info "induction-heating coupling efficiency must be positive"
                        {:field :coupling-efficiency :value coupling-efficiency})))
      (let [absorbed-power (* heating-power-W coupling-efficiency)
            absorbed-energy (* absorbed-power duration-s)
            initial (double (or initial-temperature-C ambient-C 25.0))
            delta-t (/ absorbed-energy (* thermal-mass-kg specific-heat-J-kgK))]
        (merge (screening-result input :emag :induction-heating-lumped-thermal
                                 [:lumped-workpiece-thermal-mass :constant-coupling-efficiency
                                  :no-phase-change-or-heat-loss])
               {:mode mode :input-power-W heating-power-W :absorbed-power-W absorbed-power
                :absorbed-energy-J absorbed-energy :coupling-efficiency coupling-efficiency
                :initial-temperature-C initial :temperature-rise-K delta-t
                :final-temperature-C (+ initial delta-t)})))

    (throw (ex-info "unknown electromagnetic analysis mode"
                    {:mode mode :supported [:motor :induction-heating]}))))

(defn production-des
  "Deterministic discrete-event flow-line simulation.
  A case has `:stations [{:id :cycle-time-s :availability :transport-time-s :power-kW}]`,
  `:jobs`, and optional `:arrival-interval-s`. Jobs visit every station in
  order; a station's `:transport-time-s` is applied before the next station.
  The returned makespan, utilisation, throughput, waiting, transport,
  lead-time, average WIP, and busy-time energy are computed from the event
  schedule. `:power-kW` is optional and defaults to zero."
  [{:keys [stations jobs arrival-interval-s] :or {arrival-interval-s 0.0} :as input}]
  (when-not (and (pos-int? jobs) (seq stations))
    (throw (ex-info "production DES needs positive :jobs and non-empty :stations"
                    {:jobs jobs :stations stations})))
  (nonnegative! {:arrival-interval-s arrival-interval-s} [:arrival-interval-s])
  (when-not (= (count stations) (count (set (map :id stations))))
    (throw (ex-info "production DES station :id values must be unique" {:stations stations})))
  (doseq [station stations]
    (when (nil? (:id station))
      (throw (ex-info "production DES station requires :id" {:station station})))
    (positive! station [:cycle-time-s])
    (nonnegative! {:transport-time-s (or (:transport-time-s station) 0.0)}
                  [:transport-time-s])
    (nonnegative! {:power-kW (or (:power-kW station) 0.0)} [:power-kW])
    (when-not (<= 0.0 (double (or (:availability station) 1.0)) 1.0)
      (throw (ex-info "station availability must be in [0,1]" {:station station})))
    (when (zero? (double (or (:availability station) 1.0)))
      (throw (ex-info "station availability must be positive" {:station station}))))
  (let [station-count (count stations)
        initial {:available (vec (repeat station-count 0.0))
                 :wait 0.0 :busy (vec (repeat station-count 0.0))
                 :transport 0.0 :flow 0.0 :energy 0.0}
        schedule (reduce
                  (fn [{:keys [available wait busy transport flow energy]} job]
                    (let [release (* job arrival-interval-s)
                          [available' wait' busy' transport' flow' energy' _]
                          (reduce-kv
                           (fn [[times total-wait total-busy total-transport total-flow total-energy upstream] idx station]
                             (let [transport-time (if (zero? idx) 0.0
                                                      (double (or (:transport-time-s (nth stations (dec idx))) 0.0)))
                                   arrival (if (zero? idx) release (+ upstream transport-time))
                                   start (max arrival (nth times idx))
                                   service (/ (:cycle-time-s station) (double (or (:availability station) 1.0)))
                                   finish (+ start service)]
                               [(assoc times idx finish) (+ total-wait (- start arrival))
                                (assoc total-busy idx (+ (nth total-busy idx) service))
                                (+ total-transport transport-time)
                                (if (= idx (dec station-count)) (+ total-flow (- finish release)) total-flow)
                                (+ total-energy (* (double (or (:power-kW station) 0.0)) (/ service 3600.0)))
                                finish]))
                           [available wait busy transport flow energy 0.0] (vec stations))]
                      {:available available' :wait wait' :busy busy'
                       :transport transport' :flow flow' :energy energy'}))
                  initial (range jobs))
        makespan (apply max (:available schedule))]
    (merge (screening-result input :production-des :deterministic-flow-line
                             [:single-server-per-station :FIFO-order :deterministic-cycle-time
                              :deterministic-interstation-transport])
           {:jobs jobs :makespan-s makespan
            :throughput-per-hour (/ (* jobs 3600.0) makespan)
            :mean-wait-s (/ (:wait schedule) jobs)
            :mean-transport-s (/ (:transport schedule) jobs)
            :mean-flow-time-s (/ (:flow schedule) jobs)
            ;; Little's law over the observed finite horizon: area under the
            ;; system-WIP curve is the sum of all job flow times.
            :mean-wip (/ (:flow schedule) makespan)
            :energy-kWh (:energy schedule)
            :energy-per-job-kWh (/ (:energy schedule) jobs)
            :station-utilization (mapv (fn [station busy]
                                         {:id (:id station) :utilization (/ busy makespan)})
                                       stations (:busy schedule))})))

;; ---------------------------------------------------------------------------
;; Hydrogen storage: metal-hydride desorption equilibrium (van't Hoff)
;;
;; System context: the magnesium-hydrogen-PEMFC electric-drive boundary
;; (scripts/hermes-magnesium-systems-bots/system-scope.edn) needs a
;; cartridge/reactor desorption-equilibrium contract upstream of thermal
;; control, pressure/leak CAE, and fuel-cell H2 supply sizing. This contract
;; is GENERIC: the hydride identity, enthalpy and entropy are caller-supplied
;; with mandatory provenance — no Mg/MgH2 constants are baked in here.

(def ^:private gas-constant-J-molK 8.31446261815324)
;; CODATA 2018 exact molar gas constant (defined via k_B and N_A). This is a
;; physical unit constant, not a material property, so it is the only default
;; thermodynamic number in this contract.

(defn- nonblank-string! [input k]
  (let [v (get input k)]
    (when-not (and (string? v) (re-find #"\S" v))
      (throw (ex-info "industrial CAE input must be a non-blank string"
                      {:field k :value v})))))

(defn h2-desorption
  "Metal-hydride hydrogen desorption equilibrium (van't Hoff) screening model.

  Case keys:
  - `:temperature-K` — bed temperature (required, positive).
  - `:enthalpy-desorption-J-mol` — ΔH per mol H2 (required, positive).
  - `:entropy-desorption-J-molK` — ΔS per mol H2 (required, positive).
  - `:thermo-source` — non-blank provenance string for ΔH/ΔS (required).
    The contract FAILS CLOSED without it: unprovenanced thermodynamic data
    must never enter a case.
  - `:reference-pressure-Pa` — standard-state pressure (default 1e5 Pa).
  - Optional capacity group (all-or-none): `:hydride-mass-kg`,
    `:molar-mass-hydride-kg-mol`, `:molar-mass-h2-kg-mol`,
    `:h2-per-formula-unit` (moles H2 released per mol hydride).

  Returns the equilibrium plateau pressure via
  `ln(P/P°) = ΔS/R − ΔH/(R·T)` plus, when the capacity group is given, the
  stoichiometric fully-released H2 mass. Generic hydride only: an actual
  Mg/MgH2 card (ΔH, ΔS, molar masses, validity range) is a caller-provided,
  provenance-carrying input — this repo measures none."
  [{:keys [temperature-K enthalpy-desorption-J-mol entropy-desorption-J-molK
           thermo-source reference-pressure-Pa hydride-mass-kg
           molar-mass-hydride-kg-mol molar-mass-h2-kg-mol h2-per-formula-unit]
    :or {reference-pressure-Pa 100000.0}
    :as input}]
  (positive! input [:temperature-K :enthalpy-desorption-J-mol
                    :entropy-desorption-J-molK])
  (positive! {:reference-pressure-Pa reference-pressure-Pa}
             [:reference-pressure-Pa])
  (nonblank-string! input :thermo-source)
  (let [capacity-keys [:hydride-mass-kg :molar-mass-hydride-kg-mol
                       :molar-mass-h2-kg-mol :h2-per-formula-unit]
        given (filter #(some? (get input %)) capacity-keys)]
    (when-not (or (empty? given) (= (count given) (count capacity-keys)))
      (throw (ex-info "hydride capacity group must be given all-or-none"
                      {:given given :required capacity-keys})))
    (when (seq given)
      (positive! input capacity-keys))
    (let [r gas-constant-J-molK
          ln-p (+ (/ entropy-desorption-J-molK r)
                  (- (/ enthalpy-desorption-J-mol (* r temperature-K))))
          equilibrium-pressure-Pa (* reference-pressure-Pa (Math/exp ln-p))
          h2-mass-kg (when (seq given)
                       (* hydride-mass-kg
                          (/ (* h2-per-formula-unit molar-mass-h2-kg-mol)
                             molar-mass-hydride-kg-mol)))]
      (merge (screening-result input :h2-desorption :van-t-hoff-plateau
                               [:van-t-hoff-equilibrium :single-plateau
                                :ideal-gas :standard-state-reference-pressure
                                :equilibrium-not-kinetics])
             {:temperature-K temperature-K
              :thermo-source thermo-source
              :enthalpy-desorption-J-mol enthalpy-desorption-J-mol
              :entropy-desorption-J-molK entropy-desorption-J-molK
              :reference-pressure-Pa reference-pressure-Pa
              :equilibrium-pressure-Pa equilibrium-pressure-Pa
              :equilibrium-lnPP-ref ln-p
              :capacity-h2-mass-kg h2-mass-kg}))))
(defn fatigue
  "Miner's-rule cumulative-damage fatigue over a caller-supplied load spectrum.
  Case keys: `:spectrum` — a non-empty sequence of blocks, each with
  `:stress-range-Pa` and `:cycles`; an optional per-block `:mean-stress-Pa`
  applies the caller-supplied Goodman mean-stress correction and requires
  `:ultimate-strength-Pa` on the case. The SN curve is `:basquin-b` /
  `:basquin-C` — BOTH must be supplied; this contract invents no material
  constants, so an unmeasured curve stays unmeasured.
  Returns per-block lives and damage fractions, total Miner damage for one
  spectrum pass, and the number of spectrum passes to failure."
  [{:keys [spectrum basquin-b basquin-C ultimate-strength-Pa] :as input}]
  (when (or (not (sequential? spectrum)) (empty? spectrum))
    (throw (ex-info "fatigue requires a non-empty :spectrum of load blocks"
                    {:spectrum spectrum})))
  (when-not (and (finite-number? basquin-b) (neg? (double basquin-b)))
    (throw (ex-info "Basquin exponent :basquin-b must be supplied, finite and negative"
                    {:field :basquin-b :value basquin-b})))
  (when-not (and (finite-number? basquin-C) (pos? (double basquin-C)))
    (throw (ex-info "Basquin coefficient :basquin-C must be supplied, finite and positive"
                    {:field :basquin-C :value basquin-C})))
  (let [block-results
        (mapv (fn [{:keys [stress-range-Pa cycles mean-stress-Pa] :as block}]
                (when-not (map? block)
                  (throw (ex-info "spectrum block must be a map" {:block block})))
                (positive! block [:stress-range-Pa :cycles])
                (when (and (some? mean-stress-Pa) (nil? ultimate-strength-Pa))
                  (throw (ex-info "Goodman mean-stress correction requires :ultimate-strength-Pa"
                                  {:mean-stress-Pa mean-stress-Pa})))
                (nonnegative! (cond-> block
                                mean-stress-Pa (assoc :ultimate-strength-Pa
                                                      ultimate-strength-Pa))
                              (cond-> [:stress-range-Pa]
                                mean-stress-Pa (conj :mean-stress-Pa)))
                (let [amplitude (/ stress-range-Pa 2.0)
                      goodman? (some? mean-stress-Pa)
                      _ (when (and goodman?
                                   (>= (double mean-stress-Pa)
                                       (double ultimate-strength-Pa)))
                          (throw (ex-info "mean stress must be below ultimate strength for the Goodman correction"
                                          {:mean-stress-Pa mean-stress-Pa
                                           :ultimate-strength-Pa ultimate-strength-Pa})))
                      amplitude-eff (if goodman?
                                      (/ amplitude
                                         (- 1.0 (/ mean-stress-Pa ultimate-strength-Pa)))
                                      amplitude)
                      range-eff (* 2.0 amplitude-eff)
                      life (Math/pow (/ range-eff basquin-C) (/ 1.0 basquin-b))
                      damage (/ cycles life)]
                  (assoc block
                         :stress-range-Pa stress-range-Pa :cycles cycles
                         :goodman-corrected? goodman?
                         :effective-stress-range-Pa range-eff
                         :life-cycles life :damage-fraction damage)))
              spectrum)
        damage (reduce + (map :damage-fraction block-results))]
    (merge (screening-result input :fatigue :Basquin-Miner
                             [:Basquin-SN-curve :Miner-linear-damage
                              (if (some #(contains? % :mean-stress-Pa) spectrum)
                                :Goodman-mean-stress-correction
                                :no-mean-stress-correction)])
           {:basquin-b basquin-b :basquin-C basquin-C
            :ultimate-strength-Pa ultimate-strength-Pa
            :blocks block-results
            :damage-per-pass damage
            :spectrum-passes-to-failure (if (pos? damage) (/ 1.0 damage) ##Inf)
            :fatigue-life-cycles (reduce + (map :cycles spectrum))})))

(defmethod cae/solve :cfd [case] (cfd case))
(defmethod cae/solve :fatigue [case] (fatigue case))
(defmethod cae/solve :fem [case] (fem case))
(defmethod cae/solve :process [case] (process case))
(defmethod cae/solve :materials [case] (materials case))
(defmethod cae/solve :emag [case] (emag case))
(defmethod cae/solve :production-des [case] (production-des case))
(defmethod cae/solve :h2-desorption [case] (h2-desorption case))
