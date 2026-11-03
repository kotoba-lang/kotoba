(ns cae.h2-tank-storage
  "Hydrogen TANK STORAGE STATE from measured pressure and temperature
  (reduced-order screening inventory).

  System context: the magnesium-hydrogen-PEMFC electric-drive boundary
  (scripts/hermes-magnesium-systems-bots/system-scope.edn) names a
  `:controlled-hydrogen-reactor` with a replaceable Mg/MgH2 cartridge and a
  hydrogen storage/plumbing path. The upstream contracts answer RATE and
  COST questions — `:h2-desorption-heat-demand` (how much heat a rate
  costs), `:h2-desorption` (equilibrium plateau), `:h2-desorption-kinetics`
  (how fast), and the heater-limit gate (is a rate heat-feasible). The
  vehicle plane's consumption profile emits a per-interval H2 demand. NONE
  of them answer the inventory question *how much H2 is in the tank right
  now, given the measured pressure and temperature* — which is what
  endurance, range, and refill scheduling need before the demand schedule
  can be divided against anything. This contract is that smallest
  composition step: measured (P, T) + tank geometry -> stored H2 mass.

  Genericity / provenance discipline (mirrors `cae.h2-heat-demand` and
  `cae.h2-heat-demand`'s consumers):
  - `:pressure-Pa` (ABSOLUTE, not gauge), `:temperature-K`, `:volume-m3`
    and `:molar-mass-h2-kg-mol` are CALLER-SUPPLIED with a mandatory
    non-blank `:molar-mass-source` provenance string covering the molar
    mass. The contract FAILS CLOSED without it. No tank size, fill
    pressure, or composition constant is baked in here.
  - Compressibility is opt-in and all-or-none with its provenance:
    `:compressibility-factor` (positive, dimensionless, real-gas Z) may be
    supplied together with a non-blank `:compressibility-source`. When
    absent, the IDEAL-GAS model (Z = 1) is used — this is a DECLARED
    model assumption carried on every result, never a measured constant.
  - The molar gas constant R = 8.314462618 J/(mol·K) is a CODATA exact
    definition of physical constants (N, kB), not a material property,
    and is echoed on every result.

  Model (uniform tank state at equilibrium — a screening assumption):
      n  [mol H2] = P · V / (Z · R · T)        (PV = ZnRT)
      m  [kg H2]  = n · M-H2
  Every result carries the explicit unmeasured envelope (thermal
  stratification, real-gas effects when Z was not supplied, sensor
  uncertainties, leakage integral). Endurance downstream is simply
  `:h2-mass-kg` divided by a demand rate from the vehicle plane's
  consumption profile — no new constant is invented there either."
  (:require [cae.solver :as cae.solver]))

(defn- finite-number? [x]
  (and (number? x)
       #?(:clj (Double/isFinite (double x))
          :cljs (js/isFinite x))))

(defn- positive! [input ks]
  (doseq [k ks]
    (when-not (and (finite-number? (get input k)) (pos? (double (get input k))))
      (throw (ex-info "h2-tank-storage input must be a finite positive number"
                      {:field k :value (get input k)})))))

(defn- nonblank-string! [input k]
  (let [v (get input k)]
    (when-not (and (string? v) (re-find #"\S" v))
      (throw (ex-info "h2-tank-storage input must be a non-blank string"
                      {:field k :value v})))))

(def ^:private molar-gas-constant-J-molK 8.314462618)

(defn h2-tank-storage
  "Stored hydrogen inventory of a tank from measured absolute pressure and
  temperature.

  Case keys:
  - `:pressure-Pa` — ABSOLUTE tank pressure (required, positive). A gauge
    reading must be converted by the caller; the contract refuses to guess
    the ambient reference.
  - `:temperature-K` — gas temperature (required, positive).
  - `:volume-m3` — usable gas volume (required, positive).
  - `:molar-mass-h2-kg-mol` — hydrogen molar mass (required, positive;
    caller-supplied so no isotope/composition assumption is baked in).
  - `:molar-mass-source` — non-blank provenance string for the molar mass
    (required; fail-closed without it).
  - Optional real-gas pair (all-or-none): `:compressibility-factor` (Z,
    positive) + `:compressibility-source` (non-blank). Absent pair means
    the ideal-gas assumption, declared on the result.

  Returns a `:screening-only` result with `:h2-mol`, `:h2-mass-kg`, the
  echoed gas constant, provenance, assumptions, and the explicit
  unmeasured envelope."
  [{:keys [pressure-Pa temperature-K volume-m3 molar-mass-h2-kg-mol
           molar-mass-source compressibility-factor]
    :as input}]
  (positive! input [:pressure-Pa :temperature-K :volume-m3 :molar-mass-h2-kg-mol])
  (nonblank-string! input :molar-mass-source)
  (let [z-keys [:compressibility-factor :compressibility-source]
        given  (filter #(some? (get input %)) z-keys)]
    (when-not (or (empty? given) (= (count given) (count z-keys)))
      (throw (ex-info "compressibility pair must be given all-or-none"
                      {:given given :required z-keys})))
    (when (contains? input :compressibility-factor)
      (positive! input [:compressibility-factor])
      (nonblank-string! input :compressibility-source))
    (let [z      (if (seq given) (double compressibility-factor) 1.0)
          ideal? (not (seq given))
          n-mol  (/ (* (double pressure-Pa) (double volume-m3))
                    (* z molar-gas-constant-J-molK (double temperature-K)))
          m-kg   (* n-mol (double molar-mass-h2-kg-mol))]
      (cond-> {:solver :h2-tank-storage
               :model (if ideal?
                        "uniform tank state: n = P·V / (R·T) (ideal gas)"
                        "uniform tank state: n = P·V / (Z·R·T) (real gas, caller Z)")
               :fidelity :reduced-order
               :status :screening-only
               :units :SI
               :assumptions (cond-> {:uniform-tank-state true
                                     :equilibrium true
                                     :absolute-pressure true}
                              ideal? (assoc :ideal-gas-Z-1 true)
                              (not ideal?) (assoc :caller-compressibility true))
               :ideal-gas-constant-J-molK molar-gas-constant-J-molK
               :compressibility-factor-used z
               :h2-mol n-mol
               :h2-mass-kg m-kg
               :molar-mass-source molar-mass-source
               :unmeasured (cond-> {:tank-thermal-stratification true
                                    :sensor-pressure-uncertainty true
                                    :sensor-temperature-uncertainty true
                                    :leakage-integral true
                                    :dead-volume-uncertainty true}
                             ideal? (assoc :real-gas-effects true))}
        (:case/id input) (assoc :case/id (:case/id input))
        (:case/provenance input) (assoc :case/provenance (:case/provenance input))
        (:compressibility-source input) (assoc :compressibility-source
                                               (:compressibility-source input))))))

(defmethod cae.solver/solve :h2-tank-storage [case]
  (h2-tank-storage case))
