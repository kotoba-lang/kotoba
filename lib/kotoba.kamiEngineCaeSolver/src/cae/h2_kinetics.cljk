(ns cae.h2-kinetics
  "Generic metal-hydride hydrogen DESORPTION KINETICS (transient screening).

  System context: the magnesium-hydrogen-PEMFC electric-drive boundary
  (scripts/hermes-magnesium-systems-bots/system-scope.edn) names a
  `:controlled-hydrogen-reactor`. The equilibrium contract
  (`:h2-desorption`, van't Hoff plateau) answers *whether* and *at what
  pressure* a bed desorbs; it cannot answer *how fast* — which is what
  reactor control and fuel-cell supply scheduling need. This contract is
  the smallest transient step in that direction.

  Genericity / provenance discipline (mirrors `cae.industrial/h2-desorption`):
  - The hydride identity, Arrhenius pre-exponential factor `:rate-A-per-s`
    and activation energy `:activation-energy-J-mol` are CALLER-SUPPLIED
    with a mandatory non-blank `:kinetics-source` provenance string. The
    contract FAILS CLOSED without it: unprovenanced kinetic data must
    never enter a case.
  - The equilibrium plateau pressure is a caller-supplied input
    (`:equilibrium-pressure-Pa`), typically obtained from the
    `:h2-desorption` equilibrium contract at the same bed temperature —
    this namespace never recomputes thermodynamics and bakes in no
    Mg/MgH2 constants.
  - The only default number is the CODATA 2018 exact molar gas constant
    (a physical unit constant, not a material property).

  Model (constant T and P over the window — a screening assumption that
  is carried on every result):
      k(T)   = A · exp(−Ea / (R·T))                       [1/s]
      θ      = max(0, 1 − P/P_eq)                          [dimensionless driving force]
      dx/dt  = k(T) · θ · (1 − x)                          first-order in remaining fraction
  integrated by explicit Euler over `:time-s` with step `:dt-s`. Because
  T, P and θ are constant over the window this admits the closed form
      x(t) = 1 − (1 − x0) · exp(−k(T) · θ · t)
  and every result carries `:analytic-fraction-released` plus the numeric
  solution, so the caller sees the discretization error directly (and a
  `:dt-refinement-rel-diff` between dt and dt/2 runs as convergence
  evidence). No hysteresis, slope factor, bed thermal mass, pressure
  ramp or heat-transfer coupling is modeled — all of that remains
  explicitly unmeasured here."
  (:require [cae.solver :as cae]))

(def ^:private gas-constant-J-molK 8.31446261815324)
;; CODATA 2018 exact molar gas constant (defined via k_B and N_A). Physical
;; unit constant, not a material property.

(defn- finite-number? [x]
  (and (number? x)
       #?(:clj (Double/isFinite (double x))
          :cljs (js/isFinite x))))

(defn- positive! [input ks]
  (doseq [k ks]
    (when-not (and (finite-number? (get input k)) (pos? (double (get input k))))
      (throw (ex-info "h2-kinetics input must be a finite positive number"
                      {:field k :value (get input k)})))))

(defn- nonblank-string! [input k]
  (let [v (get input k)]
    (when-not (and (string? v) (re-find #"\S" v))
      (throw (ex-info "h2-kinetics input must be a non-blank string"
                      {:field k :value v})))))

(defn h2-desorption-kinetics
  "Transient first-order metal-hydride desorption screening over one window
  of constant temperature and pressure.

  Case keys:
  - `:temperature-K` — bed temperature (required, positive).
  - `:pressure-Pa` — ambient hydrogen pressure at the bed (required, positive).
    Desorption proceeds only while this is below the equilibrium pressure;
    above it the driving force is clamped to zero (absorption is NOT modeled).
  - `:equilibrium-pressure-Pa` — plateau pressure at `:temperature-K`
    (required, positive; caller-supplied so the equilibrium contract owns
    the thermodynamics).
  - `:rate-A-per-s` — Arrhenius pre-exponential factor (required, positive).
  - `:activation-energy-J-mol` — activation energy (required, positive).
  - `:kinetics-source` — non-blank provenance string for A and Ea
    (required; fail-closed without it).
  - `:time-s` — window length (required, positive).
  - `:dt-s` — explicit Euler step (required, positive; must not exceed `:time-s`).
  - `:initial-fraction-released` — x0 in [0, 1] (default 0.0).
  - Optional capacity group (all-or-none): `:hydride-mass-kg`,
    `:molar-mass-hydride-kg-mol`, `:molar-mass-h2-kg-mol`,
    `:h2-per-formula-unit` — same stoichiometry contract as the
    `:h2-desorption` equilibrium model; when present, the released H2 mass
    is reported as `:released-h2-mass-kg` (fraction-released × capacity).

  Returns a `:screening-only` result with the rate constant, driving force,
  numeric and analytic fraction released, dt-refinement relative difference,
  and the explicit unmeasured envelope (hysteresis, slope, thermal mass,
  pressure ramp, heat transfer, absorption)."
  [{:keys [temperature-K pressure-Pa equilibrium-pressure-Pa rate-A-per-s
           activation-energy-J-mol kinetics-source time-s dt-s
           initial-fraction-released hydride-mass-kg
           molar-mass-hydride-kg-mol molar-mass-h2-kg-mol h2-per-formula-unit]
    :or {initial-fraction-released 0.0}
    :as input}]
  (let [x0 (if (and (finite-number? initial-fraction-released)
                    (<= 0.0 (double initial-fraction-released) 1.0))
             (double initial-fraction-released)
             (throw (ex-info "h2-kinetics input must be in [0, 1]"
                             {:field :initial-fraction-released
                              :value initial-fraction-released})))]
    (positive! input [:temperature-K :pressure-Pa :equilibrium-pressure-Pa
                      :rate-A-per-s :activation-energy-J-mol :time-s :dt-s])
    (when (> (double dt-s) (double time-s))
      (throw (ex-info "h2-kinetics dt-s must not exceed time-s"
                      {:dt-s dt-s :time-s time-s})))
    (nonblank-string! input :kinetics-source)
    (let [capacity-keys [:hydride-mass-kg :molar-mass-hydride-kg-mol
                       :molar-mass-h2-kg-mol :h2-per-formula-unit]
        given (filter #(some? (get input %)) capacity-keys)]
    (when-not (or (empty? given) (= (count given) (count capacity-keys)))
      (throw (ex-info "hydride capacity group must be given all-or-none"
                      {:given given :required capacity-keys})))
    (when (seq given)
      (positive! input capacity-keys))
    (let [r      gas-constant-J-molK
          k-rate (* rate-A-per-s (Math/exp (- (/ activation-energy-J-mol (* r temperature-K)))))
          theta  (max 0.0 (- 1.0 (/ pressure-Pa equilibrium-pressure-Pa)))
          k-eff  (* k-rate theta)
          n      (long (Math/ceil (/ time-s dt-s)))
          step   (/ time-s n)
          ;; explicit Euler over n uniform steps (step <= dt-s)
          x-num  (loop [i 0 x x0]
                   (if (= i n)
                     x
                     (recur (inc i) (+ x (* step k-eff (- 1.0 x))))))
          x-ana  (if (zero? k-eff)
                   x0
                   (- 1.0 (* (- 1.0 x0) (Math/exp (- (* k-eff time-s))))))
          ;; dt-refinement: same integration at half the step
          n2     (* 2 n)
          x-ref  (loop [i 0 x x0]
                   (if (= i n2)
                     x
                     (recur (inc i) (+ x (* (/ time-s n2) k-eff (- 1.0 x))))))
          rel-diff (if (pos? x-ana)
                     (/ (Math/abs (- x-ref x-num)) x-ana)
                     0.0)
          capacity (when (seq given)
                     (* hydride-mass-kg
                        (/ (* h2-per-formula-unit molar-mass-h2-kg-mol)
                           molar-mass-hydride-kg-mol)))]
      (cond-> {:solver :h2-desorption-kinetics
               :model :first-order-arrhenius-desorption
               :fidelity :reduced-order
               :status :screening-only
               :units :SI
               :assumptions [:constant-temperature-window :constant-pressure-window
                             :first-order-in-remaining-fraction :no-hysteresis
                             :no-slope-factor :no-bed-thermal-mass
                             :no-absorption :explicit-euler]
               :temperature-K temperature-K
               :pressure-Pa pressure-Pa
               :equilibrium-pressure-Pa equilibrium-pressure-Pa
               :kinetics-source kinetics-source
               :rate-A-per-s rate-A-per-s
               :activation-energy-J-mol activation-energy-J-mol
               :rate-constant-per-s k-rate
               :driving-force-theta theta
               :effective-rate-constant-per-s k-eff
               :time-s time-s
               :dt-s-used step
               :initial-fraction-released x0
               :fraction-released x-num
               :analytic-fraction-released x-ana
               :dt-refinement-rel-diff rel-diff
               :unmeasured {:hydride-hysteresis true :plateau-slope-factor true
                            :bed-thermal-mass true :pressure-ramp true
                            :heat-transfer-coupling true :absorption true
                            :reaction-order true}}
        (:case/id input)        (assoc :case/id (:case/id input))
        (:case/provenance input) (assoc :case/provenance (:case/provenance input))
        (some? capacity)        (assoc :capacity-h2-mass-kg capacity
                                       :released-h2-mass-kg (* x-ana capacity)))))))

(defmethod cae/solve :h2-desorption-kinetics [case] (h2-desorption-kinetics case))
