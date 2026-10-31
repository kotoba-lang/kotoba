(ns cae.h2-heater-limit
  "Metal-hydride HEATER-LIMITED H2 SUPPLY FEASIBILITY (steady screening gate).

  System context: the magnesium-hydrogen-PEMFC electric-drive boundary
  (scripts/hermes-magnesium-systems-bots/system-scope.edn) names a
  `:controlled-hydrogen-reactor` and a replaceable Mg/MgH2 cartridge. The
  heat-demand contract (`:h2-desorption-heat-demand`) answers *how much
  heat power a given H2 rate costs*, but not whether the reactor's heater
  can actually PAY that bill — the vehicle-plane consumers (e.g.
  kami-engine-vehicle-designer `vdesign.hydrogen/consumption-profile`)
  emit an H2 demand schedule and currently have no contract that answers
  *is this rate heat-feasible at all, and if not, what is the shortfall?*
  This contract is the smallest composition step between those two: it
  reuses the heat-demand contract verbatim (same provenance discipline,
  same unmeasured envelope) and compares its total heat power against a
  caller-supplied heater power cap.

  Genericity / provenance discipline (mirrors `cae.h2-heat-demand`):
  - Desorption enthalpy `:heat-of-desorption-J-mol` (per mol H2), H2 molar
    mass `:molar-mass-h2-kg-mol` and the heater cap `:heater-power-W` are
    CALLER-SUPPLIED. The mandatory non-blank `:heat-source` provenance
    string covers the enthalpy and molar mass; the heater cap carries its
    own `:heater-source` provenance string. Both fail closed: a heater cap
    without provenance is as unusable as an unprovenanced enthalpy.
  - No Mg/MgH2, burner, or heater-efficiency constant is baked in here.
  - The optional bed sensible-heat group passes through verbatim to the
    heat-demand contract (all-or-none, additive).

  Model (steady over the window — a screening assumption carried on every
  result):
      Q-tot  [W] = heat-demand contract (:h2-desorption-heat-demand)
      m-max  [kg H2/s] = P-heater · M-H2 / ΔH-des   (heat-limited rate)
      feasible?     = Q-tot ≤ P-heater
      shortfall [kg/s] = max(0, m-dot-demand − m-max)
  Shortfall is REPORTED, never thrown — the deficit discipline the
  vehicle plane already uses. Every result carries the heat-demand
  contract's unmeasured envelope plus this contract's own (heater
  transient/thermal-mass limits, control dynamics)."
  (:require [cae.h2-heat-demand :as heat]
            [cae.solver :as cae.solver]))

(defn- finite-number? [x]
  (and (number? x)
       #?(:clj (Double/isFinite (double x))
          :cljs (js/isFinite x))))

(defn- positive! [input ks]
  (doseq [k ks]
    (when-not (and (finite-number? (get input k)) (pos? (double (get input k))))
      (throw (ex-info "h2-heater-limit input must be a finite positive number"
                      {:field k :value (get input k)})))))

(defn- nonblank-string! [input k]
  (let [v (get input k)]
    (when-not (and (string? v) (re-find #"\S" v))
      (throw (ex-info "h2-heater-limit input must be a non-blank string"
                      {:field k :value v})))))

(defn h2-desorption-heater-limit
  "Is a demanded H2 rate heat-feasible under a heater power cap, and how
  much is short if not?

  Case keys:
  - `:h2-mass-flow-kg-s` — demanded H2 production rate (required, positive).
    Typically from a fuel-cell demand schedule (e.g. the vehicle plane's
    per-interval consumption profile).
  - `:heater-power-W` — reactor heater power cap (required, positive).
  - `:heat-of-desorption-J-mol` — enthalpy of desorption, per mol H2
    (required, positive; caller-supplied).
  - `:molar-mass-h2-kg-mol` — hydrogen molar mass (required, positive).
  - `:heat-source` — non-blank provenance string for ΔH-des and M-H2
    (required; fail-closed without it).
  - `:heater-source` — non-blank provenance string for `:heater-power-W`
    (required; fail-closed without it).
  - Optional bed sensible-heat group (all-or-none, passed through to the
    heat-demand contract): `:bed-mass-kg`, `:bed-specific-heat-J-kgK`,
    `:bed-ramp-K-s`.

  Returns a `:screening-only` result echoing the full heat-demand fields,
  plus `:heat-limited-max-h2-flow-kg-s`, `:feasible?`,
  `:h2-shortfall-kg-s` (0.0 when feasible — never an exception), the
  caller's provenance echoed, and the explicit unmeasured envelope."
  [{:keys [heater-power-W heater-source h2-mass-flow-kg-s] :as input}]
  (positive! input [:heater-power-W :h2-mass-flow-kg-s])
  (nonblank-string! input :heater-source)
  (let [inner (heat/h2-desorption-heat-demand input)
        m-max (/ (* (double heater-power-W)
                    (double (:molar-mass-h2-kg-mol input)))
                 (double (:heat-of-desorption-J-mol input)))
        q-tot (:total-heat-W inner)
        feasible? (<= (double h2-mass-flow-kg-s) m-max)
        shortfall (if feasible? 0.0 (max 0.0 (- (double h2-mass-flow-kg-s) m-max)))]
    (-> inner
        (assoc :solver :h2-desorption-heater-limit
               :model "heater-limited supply gate: m-max = P·M/ΔH; feasible? ⇔ Q-tot ≤ P"
               :heater-power-W heater-power-W
               :heater-source heater-source
               :heat-limited-max-h2-flow-kg-s m-max
               :feasible? feasible?
               :h2-shortfall-kg-s shortfall
               :composed-from :h2-desorption-heat-demand)
        (update :unmeasured assoc
                :heater-transient-limits true
                :heater-thermal-mass true
                :control-dynamics true))))

(defmethod cae.solver/solve :h2-desorption-heater-limit [case]
  (h2-desorption-heater-limit case))
