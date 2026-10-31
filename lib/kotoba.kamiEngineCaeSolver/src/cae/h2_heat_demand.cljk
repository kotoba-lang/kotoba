(ns cae.h2-heat-demand
  "Metal-hydride DESORPTION HEAT DEMAND (steady screening source term).

  System context: the magnesium-hydrogen-PEMFC electric-drive boundary
  (scripts/hermes-magnesium-systems-bots/system-scope.edn) names a
  `:controlled-hydrogen-reactor` and a replaceable Mg/MgH2 cartridge.
  Desorption is ENDOTHERMIC: sustaining an H2 production rate requires a
  heat input the reactor must supply. The equilibrium contract
  (`:h2-desorption`, van't Hoff plateau) answers whether/where the bed
  desorbs; the kinetics contract (`:h2-desorption-kinetics`) answers how
  fast; NEITHER answers *how much heat power that rate costs* — which is
  what reactor heater sizing and cartridge thermal management need before
  any thermal plane (FEM/CFD) source term can be written. This contract is
  the smallest energy-balance step in that direction.

  Genericity / provenance discipline (mirrors `cae.industrial/h2-desorption`
  and `cae.h2-kinetics`):
  - The heat of desorption `:heat-of-desorption-J-mol` (per mol H2) and the
    hydrogen molar mass `:molar-mass-h2-kg-mol` are CALLER-SUPPLIED with a
    mandatory non-blank `:heat-source` provenance string. The contract
    FAILS CLOSED without it: unprovenanced enthalpy data must never enter
    a case. No Mg/MgH2 constant is baked in here.
  - Optional bed sensible-heat group (all-or-none): `:bed-mass-kg`,
    `:bed-specific-heat-J-kgK`, `:bed-ramp-K-s` — the thermal power to
    raise the bed at a given rate (P = m·cp·dT/dt). All three must be
    present together or absent together; the group is additive with the
    desorption heat.

  Model (steady over the window — a screening assumption carried on every
  result):
      n-dot  [mol H2/s] = m-dot-H2 / M-H2
      Q-des  [W]        = n-dot · ΔH-des
      Q-sens [W]        = m-bed · cp-bed · (dT/dt)     (0 when the group is absent)
      Q-tot  [W]        = Q-des + Q-sens
  Every result carries the explicit unmeasured envelope (heat-transfer
  coupling, bed temperature gradients, hysteresis/plateau slope, absorption
  heat, kinetic coupling, pressure-ramp work)."
  (:require [cae.solver :as cae]))

(defn- finite-number? [x]
  (and (number? x)
       #?(:clj (Double/isFinite (double x))
          :cljs (js/isFinite x))))

(defn- positive! [input ks]
  (doseq [k ks]
    (when-not (and (finite-number? (get input k)) (pos? (double (get input k))))
      (throw (ex-info "h2-heat-demand input must be a finite positive number"
                      {:field k :value (get input k)})))))

(defn- nonblank-string! [input k]
  (let [v (get input k)]
    (when-not (and (string? v) (re-find #"\S" v))
      (throw (ex-info "h2-heat-demand input must be a non-blank string"
                      {:field k :value v})))))

(defn- nonnegative! [input ks]
  (doseq [k ks]
    (when-not (and (finite-number? (get input k)) (not (neg? (double (get input k)))))
      (throw (ex-info "h2-heat-demand input must be a finite non-negative number"
                      {:field k :value (get input k)})))))

(defn- screening-result
  "Attach the common traceability envelope required for every reference result."
  [input kind model assumptions]
  (cond-> {:solver kind :model model :fidelity :reduced-order
           :status :screening-only :units :SI :assumptions assumptions}
    (:case/id input) (assoc :case/id (:case/id input))
    (:case/provenance input) (assoc :case/provenance (:case/provenance input))))

(defn h2-desorption-heat-demand
  "Steady heat power required to sustain a metal-hydride H2 desorption rate.

  Case keys:
  - `:h2-mass-flow-kg-s` — H2 production rate to sustain (required, positive).
    Typically taken from the `:h2-desorption-kinetics` contract's released
    mass over its window, or from a fuel-cell demand schedule.
  - `:heat-of-desorption-J-mol` — enthalpy of desorption, per mol H2
    (required, positive; caller-supplied).
  - `:molar-mass-h2-kg-mol` — hydrogen molar mass (required, positive;
    caller-supplied so no isotope/composition assumption is baked in).
  - `:heat-source` — non-blank provenance string for ΔH-des and M-H2
    (required; fail-closed without it).
  - Optional sensible-heat group (all-or-none): `:bed-mass-kg` (positive),
    `:bed-specific-heat-J-kgK` (positive), `:bed-ramp-K-s` (non-negative)
    — adds m·cp·dT/dt to the required heat power.

  Returns a `:screening-only` result with `:h2-mol-per-s`,
  `:desorption-heat-W`, `:sensible-heat-W`, `:total-heat-W`, the caller's
  provenance echoed, and the explicit unmeasured envelope."
  [{:keys [h2-mass-flow-kg-s heat-of-desorption-J-mol molar-mass-h2-kg-mol
           heat-source bed-mass-kg bed-specific-heat-J-kgK bed-ramp-K-s]
    :as input}]
  (positive! input [:h2-mass-flow-kg-s :heat-of-desorption-J-mol :molar-mass-h2-kg-mol])
  (nonblank-string! input :heat-source)
  (let [sens-keys [:bed-mass-kg :bed-specific-heat-J-kgK :bed-ramp-K-s]
        given (filter #(some? (get input %)) sens-keys)]
    (when-not (or (empty? given) (= (count given) (count sens-keys)))
      (throw (ex-info "bed sensible-heat group must be given all-or-none"
                      {:given given :required sens-keys})))
    (when (seq given)
      (positive! input [:bed-mass-kg :bed-specific-heat-J-kgK])
      (nonnegative! input [:bed-ramp-K-s]))
    (let [h2-mol-s (/ (double h2-mass-flow-kg-s) (double molar-mass-h2-kg-mol))
          q-des    (* h2-mol-s (double heat-of-desorption-J-mol))
          q-sens   (if (seq given)
                     (* (double bed-mass-kg)
                        (double bed-specific-heat-J-kgK)
                        (double bed-ramp-K-s))
                     0.0)]
      (assoc (screening-result
              input :h2-desorption-heat-demand
              "steady endothermic heat demand: Q = n-dot · ΔH-des (+ m·cp·dT/dt)"
              {:constant-temperature-pressure-window true
               :steady-rate true})
             :h2-mol-per-s        h2-mol-s
             :desorption-heat-W   q-des
             :sensible-heat-W     q-sens
             :total-heat-W        (+ q-des q-sens)
             :heat-source         heat-source
             :unmeasured {:heat-transfer-coupling true
                          :bed-temperature-gradients true
                          :hydride-hysteresis true
                          :plateau-slope-factor true
                          :absorption-heat true
                          :kinetic-coupling true
                          :pressure-ramp-work true}))))

(defmethod cae.solver/solve :h2-desorption-heat-demand [case]
  (h2-desorption-heat-demand case))