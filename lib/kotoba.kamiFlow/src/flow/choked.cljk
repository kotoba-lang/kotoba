(ns flow.choked
  "Executable compressible ideal-gas restriction/leak contract for the
  magnesium-hydrogen-PEMFC electric-drive system's `:fluid-pressure-and-leak-cae`
  design domain (composes with `flow.pressure`; no dependency on it).

  Removes the demonstrated downstream block recorded in the open
  `flow.pressure` contract: its incompressible `restriction-mass-flow` is
  explicitly valid only for small pressure ratios and *under-predicts*
  choked flow. Cartridge / reactor / PEMFC hydrogen leak paths routinely
  sit at large pressure ratios, so this namespace provides the
  compressible model with an explicit regime determination.

  Model (one-dimensional, isentropic ideal-gas orifice, SI units carried
  in result keys):
    pressure ratio  pr = Pd / P0   (downstream / upstream, absolute)
    critical ratio  pr* = (2/(k+1))^(k/(k-1))
    subcritical (pr > pr*):
      mdot = Cd*A*P0*sqrt(2k/((k-1)*R*T0)) * sqrt(pr^(2/k) - pr^((k+1)/k))
    choked (pr <= pr*):
      mdot = Cd*A*P0*sqrt(k/(R*T0)) * (2/(k+1))^((k+1)/(2*(k-1)))

  Provenance discipline (same policy as `flow.pressure` / `flow.pump`):
    - Every physical quantity is an explicit caller input. This namespace
      never defaults a gas constant, gamma, temperature, pressure, area,
      or discharge coefficient. The specific-gas constant for hydrogen
      (4124 J/(kg*K)) and gamma (1.4 for diatomic ideal gas) are commonly
      cited textbook values, but the CALLER supplies them so the
      provenance of each value travels with the case. Unknown values
      stay unknown.
    - Absolute pressures and temperatures are required (P0 > Pd >= 0,
      T0 > 0): the ideal-gas model is meaningless otherwise.
    - The caller decides whether the ideal-gas + isentropic assumptions
      are valid for their path (sharp orifice, adiabatic, no heat
      transfer); this contract does not silently stretch them.

  Pure data in, pure data out: no I/O, no globals, portable .cljc.")

;; ---------------------------------------------------------------------------
;; Validation helpers

(defn- require-pos!
  "Throws when any of the keyed values is not a positive finite number."
  [m ks]
  (doseq [k ks]
    (let [v (get m k ::missing)]
      (when (= v ::missing)
        (throw (ex-info (str "missing required input: " (name k)) {:key k})))
      (when-not (and (number? v) (pos? v))
        (throw (ex-info (str "input must be a positive number: " (name k))
                        {:key k :value v}))))))

(defn- require-nonneg!
  [m ks]
  (doseq [k ks]
    (let [v (get m k ::missing)]
      (when (= v ::missing)
        (throw (ex-info (str "missing required input: " (name k)) {:key k})))
      (when-not (and (number? v) (>= v 0.0))
        (throw (ex-info (str "input must be a non-negative number: " (name k))
                        {:key k :value v}))))))

;; ---------------------------------------------------------------------------
;; Regime determination

(defn critical-pressure-ratio
  "Critical pressure ratio pr* = (2/(k+1))^(k/(k-1)) for a caller-supplied
  ratio of specific heats `gamma` (dimensionless, > 1). Returns
  `{:critical-ratio <float>}`."
  [gamma]
  (when-not (and (number? gamma) (> (double gamma) 1.0))
    (throw (ex-info "gamma must be > 1" {:key :gamma :value gamma})))
  (let [g (double gamma)]
    {:critical-ratio (Math/pow (/ 2.0 (inc g)) (/ g (dec g)))}))

(defn choked?
  "True when the caller-supplied pressure ratio `pr` (Pd/P0, dimensionless,
  >= 0) is at or below the critical ratio for `gamma` — i.e. the flow is
  choked. Returns a boolean."
  [pr gamma]
  (require-nonneg! {:pr pr} [:pr])
  (let [{:keys [critical-ratio]} (critical-pressure-ratio gamma)]
    (<= (double pr) critical-ratio)))

;; ---------------------------------------------------------------------------
;; Mass flow

(defn restriction-mass-flow
  "Compressible ideal-gas mass flow through a restriction (orifice / leak
  path), with explicit regime determination. All inputs required, SI:

    :discharge-coefficient  Cd, dimensionless (0 < Cd <= 1, caller-provided)
    :area-m2                restriction area, m^2 (> 0)
    :p0-pa                  upstream absolute stagnation pressure, Pa (> 0)
    :pd-pa                  downstream absolute static pressure, Pa (>= 0)
    :t0-k                   upstream absolute stagnation temperature, K (> 0)
    :gas-constant-r         specific gas constant R, J/(kg*K) (> 0)
    :gamma                  ratio of specific heats k = cp/cv, dimensionless (> 1)

  Returns:

    {:regime :choked | :subcritical
     :pressure-ratio pr                    Pd/P0
     :critical-ratio pr*                   (2/(k+1))^(k/(k-1))
     :mass-flow-kg-s mdot                  kg/s
     :choked? boolean}

  The subcritical and choked branches agree continuously at pr = pr*
  (verified in the tests to machine epsilon) — the regime switch does not
  introduce a discontinuity in the reported mass flow.

  Validity (caller's responsibility to confirm per path): ideal gas,
  isentropic acceleration to the throat, Cd absorbing viscous/geometry
  effects. Real-gas effects at very high pressures are NOT modeled and
  are not silently corrected here."
  [{:keys [discharge-coefficient area-m2 p0-pa pd-pa t0-k gas-constant-r
           gamma]
    :as in}]
  (require-pos! in [:discharge-coefficient :area-m2 :p0-pa :t0-k
                    :gas-constant-r :gamma])
  (require-nonneg! in [:pd-pa])
  (when (> (double discharge-coefficient) 1.0)
    (throw (ex-info "discharge-coefficient must be <= 1"
                    {:key :discharge-coefficient :value discharge-coefficient})))
  (when (> (double pd-pa) (double p0-pa))
    (throw (ex-info "downstream pressure must not exceed upstream pressure"
                    {:key :pd-pa :value pd-pa})))
  (let [cd (double discharge-coefficient)
        a (double area-m2)
        p0 (double p0-pa)
        pd (double pd-pa)
        t0 (double t0-k)
        r (double gas-constant-r)
        g (double gamma)
        pr (/ pd p0)
        pr* (Math/pow (/ 2.0 (inc g)) (/ g (dec g)))
        choked (<= pr pr*)
        mdot
        (if choked
          ;; choked branch
          (* cd a p0 (Math/sqrt (/ g (* r t0)))
             (Math/pow (/ 2.0 (inc g)) (/ (inc g) (* 2.0 (dec g)))))
          ;; subcritical branch
          (* cd a p0 (Math/sqrt (/ (* 2.0 g) (* (dec g) r t0)))
             (Math/sqrt (- (Math/pow pr (/ 2.0 g))
                           (Math/pow pr (/ (inc g) g))))))]
    {:regime (if choked :choked :subcritical)
     :pressure-ratio pr
     :critical-ratio pr*
     :mass-flow-kg-s mdot
     :choked? choked}))
