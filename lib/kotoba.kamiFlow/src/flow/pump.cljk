(ns flow.pump
  "Executable pump operating-point contract for the magnesium-hydrogen-PEMFC
  electric-drive system's coolant/H2-loop fluid domain (composes with the
  `flow.pressure` pressure-drop contract; no dependency on it).

  Scope: the intersection of a caller-supplied quadratic pump curve and a
  caller-supplied quadratic system curve, plus hydraulic/shaft power at that
  operating point. Closed-form, no iteration.

  Provenance discipline (same policy as `flow.pressure`):
    - Every physical quantity is an explicit caller input. This namespace
      never defaults a density, a gravity value, a shutoff head, a pump
      coefficient, a system resistance, or an efficiency. Unknown values
      stay unknown.
    - `:gravity` is required; callers using standard gravity pass the
      defined constant 9.80665 m/s^2 themselves.
    - Pump efficiency is optional. When absent, shaft power is NOT reported
      (reported as nil) — an unmeasured efficiency must not be silently
      assumed.

  Model (SI units carried in the result keys):
    pump curve    Hp(Q) = :shutoff-head-m  -  :pump-coefficient * Q^2
    system curve  Hs(Q) = :static-head-m   +  :system-coefficient * Q^2
    intersection  Hp(Q*) = Hs(Q*)  =>
        Q* = sqrt((shutoff-head-m - static-head-m)
                  / (pump-coefficient + system-coefficient))
    hydraulic power  P = rho * g * Q* * H(Q*)
    shaft power      P_shaft = P / eta   (only when :efficiency given)

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
;; Curve evaluation

(defn pump-head
  "Pump curve head in m at volumetric flow `q-m3s`:
      Hp(Q) = shutoff-head-m - pump-coefficient * Q^2
  Both coefficients are caller-supplied provenance. Returns
  `{:head-m <float>}`. A negative head (beyond runout of the quadratic
  fit) is returned as-is — callers decide feasibility."
  [{:keys [shutoff-head-m pump-coefficient] :as in} q-m3s]
  (require-pos! in [:shutoff-head-m :pump-coefficient])
  (require-nonneg! {:q q-m3s} [:q])
  (let [q (double q-m3s)]
    {:head-m (- (double shutoff-head-m) (* (double pump-coefficient) q q))}))

(defn system-head
  "System curve head in m at volumetric flow `q-m3s`:
      Hs(Q) = static-head-m + system-coefficient * Q^2
  Returns `{:head-m <float>}`."
  [{:keys [static-head-m system-coefficient] :as in} q-m3s]
  (require-pos! in [:system-coefficient])
  (require-nonneg! in [:static-head-m])
  (require-nonneg! {:q q-m3s} [:q])
  (let [q (double q-m3s)]
    {:head-m (+ (double static-head-m) (* (double system-coefficient) q q))}))

;; ---------------------------------------------------------------------------
;; Operating point (closed form)

(defn operating-point
  "Closed-form operating point of a quadratic pump curve against a quadratic
  system curve. All inputs required except `:efficiency` (optional, in
  (0, 1]):

    :shutoff-head-m      pump shutoff head H0, m (> 0)
    :pump-coefficient    pump curve resistance coefficient a, m/(m^3/s)^2 (> 0)
    :static-head-m       system static head, m (>= 0)
    :system-coefficient  system curve resistance coefficient k, m/(m^3/s)^2 (> 0)
    :density             fluid density, kg/m^3 (> 0)
    :gravity             gravitational acceleration, m/s^2 (> 0)
    :efficiency          optional total pump efficiency eta, dimensionless
                         (0 < eta <= 1). Absent => shaft power unmeasured.

  Returns, when H0 > static head (a positive-flow intersection exists):

    {:feasible? true
     :flow-m3s Q*              volumetric operating point, m^3/s
     :head-m H(Q*)             head at the operating point, m
     :hydraulic-power-w rho*g*Q*H, W
     :shaft-power-w P/eta or nil when :efficiency absent
     :head-residual-m          |Hp(Q*) - Hs(Q*)| acceptance check (~ machine eps)

  When H0 <= static head the pump can never exceed the static lift:
  returns `{:feasible? false :reason ...}` — an explicit infeasibility,
  not an invented flow."
  [{:keys [shutoff-head-m pump-coefficient static-head-m system-coefficient
           density gravity efficiency]
    :as in}]
  (require-pos! in [:shutoff-head-m :pump-coefficient :system-coefficient
                    :density :gravity])
  (require-nonneg! in [:static-head-m])
  (when (some? efficiency)
    (when-not (and (number? efficiency) (pos? efficiency) (<= efficiency 1.0))
      (throw (ex-info "efficiency must be in (0, 1]"
                      {:key :efficiency :value efficiency}))))
  (let [h0 (double shutoff-head-m)
        a (double pump-coefficient)
        hs (double static-head-m)
        k (double system-coefficient)]
    (if (<= h0 hs)
      {:feasible? false
       :reason (str "shutoff-head-m (" h0 ") <= static-head-m (" hs
                    "): no positive-flow intersection exists")}
      (let [q (Math/sqrt (/ (- h0 hs) (+ a k)))
            hp (- h0 (* a q q))
            hsys (+ hs (* k q q))
            head-residual (Math/abs (- hp hsys))
            rho (double density)
            g (double gravity)
            p-hyd (* rho g q hp)
            p-shaft (when (some? efficiency) (/ p-hyd (double efficiency)))]
        {:feasible? true
         :flow-m3s q
         :head-m hp
         :hydraulic-power-w p-hyd
         :shaft-power-w p-shaft
         :head-residual-m head-residual}))))
