(ns motor.esc
  "ESC (inverter) feasibility of one torque-speed operating point against a DC
  bus (:esc-feasibility) and of a whole torque-speed drive profile (:drive-feasibility).

  This is the missing link between the bus plane and the mechanical planes of
  this library: `motor.dcbus` treats the traction load as an already-net kW
  number and explicitly leaves converter losses/limits to another plane;
  `motor.solver` / `motor.envelope` speak torque and speed. This contract takes
  ONE operating point (torque, speed) and the machine + ESC electrical
  parameters, and answers: can this ESC deliver this torque at this speed from
  this bus?

  No physical constant is invented here. Everything that sets a limit or a
  gain is REQUIRED from the caller:

    :torque-Nm       demanded shaft torque, N·m (>= 0; braking is out of scope)
    :rpm             shaft speed, rpm (>= 0)
    :kt-Nm-per-A     motor torque constant, N·m per ampere
    :ke-Vs-per-rad   motor back-EMF constant, V·s per rad/s. NOT assumed equal
                     to :kt-Nm-per-A: phase conventions (RMS vs peak, phase vs
                     line) make the identity convention-dependent, so the
                     caller supplies the constant in the same convention used
                     for :r-phase-ohm and :v-ceiling-V.
    :r-phase-ohm     winding resistance seen by the ESC (same convention)
    :i-max-A         ESC current limit, A
    :v-ceiling-V     maximum voltage magnitude the ESC can present to the
                     winding from this bus, V. The modulation strategy (SVPWM,
                     six-step, ...) is the caller's decision — this contract
                     does not assume sqrt(3)·Vdc or any modulation factor.

  Model: quasi-static DC-equivalent. i = T/kt; back-EMF e = ke·omega; the
  voltage the ESC must present is v = e + i·R; electrical input power is
  e·i + i²R; mechanical power is T·omega. Copper loss is the only electrical
  loss modeled. Iron loss, mechanical (friction/windage) loss, switching loss,
  and ESC thermal capability are real and unmeasured here — the result marks
  them `:unmeasured` so a consumer cannot read the reported efficiency as a
  measured one."
  (:require [cae.solver :as cae]))

(defn- require-num
  [m key & [allow-zero?]]
  (let [v (get m key)]
    (when-not (and (number? v)
                   (if allow-zero? (>= v 0) (pos? v)))
      (throw (ex-info (str "esc needs a positive number for " (name key)
                           (when allow-zero? " (zero allowed)"))
                      {:key key :value v})))
    (double v)))

(defn solve
  "Feasibility of one operating point. See the namespace docstring for the
  required case keys — none have defaults, by design.

  Returns:
    :omega-rad-s    shaft speed, rad/s
    :i-A            phase current magnitude implied by the torque demand, A
    :back-emf-V     back-EMF magnitude at :rpm, V (caller's convention)
    :v-required-V   voltage the ESC must present, V (= e + i·R)
    :p-mech-kW      shaft power, kW
    :p-elec-kW      electrical input power (e·i + i²R), kW
    :copper-loss-kW i²R, kW
    :eff            p-mech/p-elec (nil when p-elec is zero)
    :current-ok?    i <= :i-max-A
    :voltage-ok?    v-required <= :v-ceiling-V
    :feasible?      both above
    :headroom-A     :i-max-A - :i-A (may be negative)
    :headroom-V     :v-ceiling-V - :v-required-V (may be negative)
    :unmeasured     losses this model does not capture
    :solver         :esc-feasibility"
  [case]
  (let [t   (require-num case :torque-Nm true)
        rpm (require-num case :rpm true)
        kt  (require-num case :kt-Nm-per-A)
        ke  (require-num case :ke-Vs-per-rad)
        r   (require-num case :r-phase-ohm)
        imax (require-num case :i-max-A)
        vceil (require-num case :v-ceiling-V)
        omega (* rpm (/ (* 2.0 Math/PI) 60.0))
        i (/ t kt)
        e (* ke omega)
        v-req (+ e (* i r))
        p-mech (* t omega)
        cu (* i i r)
        p-elec (+ (* e i) cu)
        eff (when (pos? p-elec) (/ p-mech p-elec))
        i-ok (<= i imax)
        v-ok (<= v-req vceil)]
    {:omega-rad-s omega
     :i-A i
     :back-emf-V e
     :v-required-V v-req
     :p-mech-kW (/ p-mech 1000.0)
     :p-elec-kW (/ p-elec 1000.0)
     :copper-loss-kW (/ cu 1000.0)
     :eff eff
     :current-ok? i-ok
     :voltage-ok? v-ok
     :feasible? (and i-ok v-ok)
     :headroom-A (- imax i)
     :headroom-V (- vceil v-req)
     :unmeasured [:iron-loss :friction-windage-loss :switching-loss
                  :esc-thermal-derating :regeneration-braking]
     :solver :esc-feasibility}))
(defn- require-profile
  [profile]
  (when-not (and (sequential? profile) (seq profile))
    (throw (ex-info "esc: :profile must be a non-empty sequential of {:rpm .. :torque-Nm ..} points"
                    {:profile profile})))
  (when-not (every? (fn [pt]
                      (and (map? pt)
                           (number? (:rpm pt))
                           (number? (:torque-Nm pt))))
                    profile)
    (throw (ex-info "esc: :profile must contain only {:rpm .. :torque-Nm ..} maps"
                    {:profile profile}))))

(defn drive-feasibility
  "Verify a motor + ESC over a uniformly-sampled, torque-speed drive profile —
  the mission-level companion to `solve`, which checks ONE operating point.
  Composes `solve` per point (identical quasi-static DC-equivalent math, no
  physical constant is invented) and integrates electrical, mechanical, and
  copper energy exactly: E = P*dt over each uniform interval.

  case:
    :profile       non-empty sequential of {:rpm r :torque-Nm t} operating
                   points (r >= 0, t >= 0; a 0/0 idle point is allowed), each
                   held for :dt-s seconds.
    :dt-s          uniform sample interval, seconds, > 0.
    :kt-Nm-per-A / :ke-Vs-per-rad / :r-phase-ohm / :i-max-A / :v-ceiling-V
                   the same ESC+machine constants as `solve`, REQUIRED with no
                   defaults (shared across the whole profile; validated per
                   point by `solve`).

  Returns:
    {:solver :drive-feasibility
     :points [{:i :rpm :torque-Nm ...every `solve` field, plus
              :elec-kWh :mech-kWh :copper-kWh} ...]
     :energy {:elec-kWh :mech-kWh :copper-kWh :overall-eff}
     :all-feasible?    boolean (every point feasible?)
     :infeasible-count int
     :duration-s       dt-s x profile length
     :unmeasured       union of point-level losses `solve` does not model
     :provenance       {:dt-s .. :profile-count ..}}

  Refusals (fail closed): empty/non-map :profile, non-positive :dt-s, or a
  missing/non-physical electrical constant (surfaced by `solve` per point)."
  [{:keys [profile dt-s] :as case}]
  (require-profile profile)
  (when-not (and (number? dt-s) (pos? dt-s))
    (throw (ex-info "esc: :dt-s must be a positive number of seconds"
                    {:dt-s dt-s})))
  (let [esc-params (select-keys case
                                [:kt-Nm-per-A :ke-Vs-per-rad :r-phase-ohm
                                 :i-max-A :v-ceiling-V])
        dt-h  (/ (double dt-s) 3600.0)
        pts   (mapv (fn [i pt]
                      (let [r (solve (merge esc-params
                                            {:torque-Nm (:torque-Nm pt)
                                             :rpm       (:rpm pt)}))]
                        (assoc r
                               :i i
                               :rpm (:rpm pt)
                               :torque-Nm (:torque-Nm pt)
                               :elec-kWh   (* (:p-elec-kW r) dt-h)
                               :mech-kWh   (* (:p-mech-kW r) dt-h)
                               :copper-kWh (* (:copper-loss-kW r) dt-h))))
                    (range)
                    profile)
        elec   (reduce + 0.0 (map :elec-kWh pts))
        mech   (reduce + 0.0 (map :mech-kWh pts))
        copper (reduce + 0.0 (map :copper-kWh pts))
        eff    (when (pos? elec) (/ mech elec))]
    {:solver :drive-feasibility
     :points pts
     :energy {:elec-kWh elec :mech-kWh mech :copper-kWh copper :overall-eff eff}
     :all-feasible? (every? :feasible? pts)
     :infeasible-count (count (remove :feasible? pts))
     :duration-s (* (double dt-s) (count pts))
     :unmeasured (vec (distinct (reduce into [] (map :unmeasured pts))))
     :provenance {:dt-s (double dt-s) :profile-count (count pts)}}))

(defmethod cae/solve :esc-feasibility [case] (solve case))
(defmethod cae/solve :drive-feasibility [case] (drive-feasibility case))