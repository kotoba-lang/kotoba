(ns motor.dcbus
  "DC-bus power balance + buffer-battery SoC (:dcbus-balance).

  This is the contract the kami-engine-motor README documents and that
  `motor.esc` composes against as an existing bus plane ('the already-net
  kW number' that converter losses/limits are the next plane up from). On
  main the namespace was documented but never landed — PR #4 added only the
  README section. This file implements exactly the documented contract so a
  caller (a vehicle energy-flow designer on the `:dc-bus` / `:buffer-battery`
  boundary, or a motor sizing composition) actually has something to call.

  Contract (as documented, preserved verbatim in behavior):

    Per-interval split of a demand series between the fuel cell (capped
    at `:p-fc-max-kW`) and the buffer battery (capped by
    `:p-bat-dis-max-kW` / `:p-bat-chg-max-kW`, confined to the
    `:soc-min`..`:soc-max` window), with a uniform `:dt-h`. Unmet power
    and regen power that cannot be absorbed are reported per interval
    and summed — never silently shifted onto another component.

  Dispatch policy (deterministic, disclosed):
    - positive demand: the fuel cell serves min(demand, :p-fc-max-kW);
      the deficit above the fc rating comes from the battery, bounded by
      the discharge cap AND the deliverable energy to `:soc-min`. Anything
      still unmet (fc exhausted + battery at `:soc-min` or discharge-capped)
      is reported as `:unmet-kw` — never silently absorbed by a guessed
      third source.
    - negative demand (regen): the fc contributes nothing and the regen
      flow charges the battery, bounded by the charge cap AND the headroom
      to `:soc-max`. Regen that cannot be absorbed is reported per interval
      as `:regen-not-absorbed-kw` and summed — never dumped into a resistor
      the model did not declare.

  The bus is idealized LOSSLESS: converter efficiency, battery round-trip
  loss, and the fuel-cell partial-load curve are all declared `:unmeasured`
  on every result, so a consumer cannot read the bookkeeping as a measured
  efficiency claim. No physical constant is invented here — every limit is a
  caller-supplied number and only conservation-of-energy arithmetic runs.

  Refusals (fail closed): non-sequential/non-numeric demand, non-positive
  `:p-fc-max-kW`, non-positive `:p-bat-dis-max-kW` / `:p-bat-chg-max-kW`,
  non-positive `:dt-h`, `:soc-min` / `:soc-max` outside [0,∞) or
  `:soc-min` > `:soc-max`, `:soc-init` outside the `:soc-min`..`:soc-max`
  window.

  Registers `:dcbus-balance` on the shared `cae.solver/solve` contract."
  (:require [cae.solver :as cae]))

(defn- finite-num? [x]
  ;; NaN is the only number not equal to itself.
  (and (number? x) (== x x) (not= x ##Inf) (not= x ##-Inf)))

(defn- finite-nonneg? [x]
  (and (finite-num? x) (>= x 0.0)))

(defn- pos-num [x]
  (and (finite-num? x) (pos? x)))

(defn- require-number-seq [xs what]
  (when-not (and (sequential? xs) (seq xs))
    (throw (ex-info (str "dcbus: " what " must be a non-empty sequential demand series (kW)")
                    {what xs})))
  (doseq [[i v] (map-indexed vector xs)]
    ;; demand may be negative (regen into the bus) — only non-finite values refuse
    (when-not (finite-num? v)
      (throw (ex-info (str "dcbus: " what " interval " i " is not a finite number")
                      {:index i :value v :what what})))))

(defn balance
  "Power-balance a demand series against a capped fuel cell and a buffer
  battery confined to the `:soc-min`..`:soc-max` window.

  case:
    :demand-kw          sequential per-interval net bus demand (kW); positive
                        = drive load, negative = regen returning to the bus.
    :dt-h               uniform interval length (hours), > 0.
    :p-fc-max-kW        fuel-cell rating cap (kW), > 0. The fc serves
                        min(demand, rating) on positive intervals only.
    :p-bat-dis-max-kW   battery discharge cap (kW), > 0.
    :p-bat-chg-max-kW   battery charge cap (kW), > 0.
    :soc-min-kWh        battery SoC window lower bound (kWh), >= 0.
    :soc-max-kWh        battery SoC window upper bound (kWh), >= :soc-min-kWh.
    :soc-init-kWh       starting SoC (kWh), inside the window. Defaults to
                        :soc-max-kWh (full) when omitted.

  Returns
    {:solver :dcbus-balance
     :intervals [{:i :demand-kw :fc-kw :batt-dis-kw :batt-chg-kw
                  :soc-end-kWh :unmet-kw :regen-not-absorbed-kw} ...]
     :energy {:demand-kWh :fc-kWh :batt-discharge-kWh :batt-charge-kWh
              :unmet-kWh :regen-not-absorbed-kWh}
     :soc {:init-kWh :min-kWh :end-kWh}
     :feasible? boolean   ; no unmet power AND no unabsorbed regen
     :provenance {:p-fc-max-kW .. :p-bat-dis-max-kW .. :p-bat-chg-max-kW ..
                  :soc-min-kWh .. :soc-max-kWh .. :soc-init-kWh .. :dt-h ..}
     :unmeasured {:bus-converter-losses true :battery-round-trip-loss true
                  :fc-partial-load-curve true}}"
  [{:keys [demand-kw dt-h p-fc-max-kW p-bat-dis-max-kW p-bat-chg-max-kW
           soc-min-kWh soc-max-kWh soc-init-kWh]}]
  (require-number-seq demand-kw :demand-kw)
  (when-not (pos-num dt-h)
    (throw (ex-info "dcbus: :dt-h must be a positive number of hours" {:dt-h dt-h})))
  (doseq [[k v] [[:p-fc-max-kW p-fc-max-kW]
                 [:p-bat-dis-max-kW p-bat-dis-max-kW]
                 [:p-bat-chg-max-kW p-bat-chg-max-kW]]]
    (when-not (pos-num v)
      (throw (ex-info (str "dcbus: " (name k) " must be a positive number (kW)")
                      {k v}))))
  (when-not (and (number? soc-min-kWh) (finite-nonneg? soc-min-kWh))
    (throw (ex-info "dcbus: :soc-min-kWh must be a finite number >= 0"
                    {:soc-min-kWh soc-min-kWh})))
  (when-not (and (number? soc-max-kWh) (finite-nonneg? soc-max-kWh)
                 (>= soc-max-kWh soc-min-kWh))
    (throw (ex-info "dcbus: :soc-max-kWh must be a finite number >= :soc-min-kWh"
                    {:soc-min-kWh soc-min-kWh :soc-max-kWh soc-max-kWh})))
  (let [fc-max  (double p-fc-max-kW)
        dis-max (double p-bat-dis-max-kW)
        chg-max (double p-bat-chg-max-kW)
        smin    (double soc-min-kWh)
        smax    (double soc-max-kWh)
        s-init  (if (nil? soc-init-kWh)
                  smax
                  (do (when-not (and (number? soc-init-kWh)
                                     (finite-nonneg? soc-init-kWh)
                                     (<= smin soc-init-kWh smax))
                        (throw (ex-info
                                "dcbus: :soc-init-kWh must be inside the :soc-min..:soc-max window"
                                {:soc-init-kWh soc-init-kWh
                                 :soc-min-kWh soc-min-kWh
                                 :soc-max-kWh soc-max-kWh})))
                      (double soc-init-kWh)))
        step    (fn [{:keys [soc] :as acc} [i demand]]
                  (let [demand (double demand)
                        dt-s   (* dt-h 3600.0)
                        ;; dispatch
                        fc-kw (if (pos? demand) (min demand fc-max) 0.0)
                        deficit0 (- demand fc-kw)
                        ;; discharge: cover deficit, bounded by cap and soc floor
                        deliverable-dis (* (- soc smin) (/ 3600.0 dt-s))
                        batt-dis (if (pos? deficit0)
                                   (min deficit0 dis-max deliverable-dis)
                                   0.0)
                        soc-after-dis (- soc (* batt-dis dt-s (/ 3600.0)))
                        unmet (max 0.0 (- deficit0 batt-dis))
                        ;; regen / charge: negative demand charges battery, bounded
                        ;; by charge cap and soc ceiling
                        headroom (* (- smax soc-after-dis) (/ 3600.0 dt-s))
                        regen-in (if (neg? demand) (- demand) 0.0)
                        batt-chg (min regen-in chg-max headroom)
                        soc-end (+ soc-after-dis (* batt-chg dt-s (/ 3600.0)))
                        regen-unabs (- regen-in batt-chg)
                        row {:i i
                             :demand-kw demand
                             :fc-kw fc-kw
                             :batt-dis-kw batt-dis
                             :batt-chg-kw batt-chg
                             :soc-end-kWh soc-end
                             :unmet-kw unmet
                             :regen-not-absorbed-kw (max 0.0 regen-unabs)}]
                    (-> acc
                        (update :intervals conj row)
                        (update :min-soc min soc-end)
                        (update :unmet-kWh + (* unmet dt-h))
                        (update :regen-kWh + (* (max 0.0 regen-unabs) dt-h))
                        (update :batt-dis-kWh + (* batt-dis dt-h))
                        (update :batt-chg-kWh + (* batt-chg dt-h))
                        (update :fc-kWh + (* fc-kw dt-h))
                        (update :demand-kWh + (* demand dt-h))
                        (assoc :soc soc-end))))
        init {:intervals [] :min-soc s-init :soc s-init
              :unmet-kWh 0.0 :regen-kWh 0.0 :batt-dis-kWh 0.0
              :batt-chg-kWh 0.0 :fc-kWh 0.0 :demand-kWh 0.0}
        out  (reduce step init (map-indexed vector demand-kw))
        rows (:intervals out)]
    {:solver :dcbus-balance
     :intervals rows
     :energy {:demand-kWh (:demand-kWh out)
              :fc-kWh (:fc-kWh out)
              :batt-discharge-kWh (:batt-dis-kWh out)
              :batt-charge-kWh (:batt-chg-kWh out)
              :unmet-kWh (:unmet-kWh out)
              :regen-not-absorbed-kWh (:regen-kWh out)}
     :soc {:init-kWh s-init :min-kWh (:min-soc out) :end-kWh (:soc out)}
     :feasible? (and (zero? (:unmet-kWh out)) (zero? (:regen-kWh out)))
     :provenance {:p-fc-max-kW (double p-fc-max-kW)
                  :p-bat-dis-max-kW (double p-bat-dis-max-kW)
                  :p-bat-chg-max-kW (double p-bat-chg-max-kW)
                  :soc-min-kWh smin
                  :soc-max-kWh smax
                  :soc-init-kWh s-init
                  :dt-h (double dt-h)}
     :unmeasured {:bus-converter-losses true
                  :battery-round-trip-loss true
                  :fc-partial-load-curve true}}))

(defmethod cae/solve :dcbus-balance [case] (balance case))