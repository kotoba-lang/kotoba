(ns echem.stack-thermal
  "Steady stack heat balance for the ROM PEM fuel cell (:rom-fc-stack-heat).
  The polarization ROM (`echem.solver`) reports electrical power and LHV
  efficiency but no heat term, so coolant-loop sizing (stack test cell,
  vehicle thermal management, EOL `coolant-fill` process) has nothing to
  compose. This contract adds the smallest steady energy-balance step:

    Q-dot = P-el * (1/eta - 1)

  where eta is the ROM's LHV efficiency and P-el its electrical power. The
  identity is exact given the ROM's own numbers — it re-uses `:eff-LHV` and
  `:stack-kW` from `echem.solver/solve` verbatim and invents nothing.

  Idealization, declared on every result: ALL non-electrical energy is
  carried by the coolant (no radiation/conduction/ambient losses, no
  cathode exhaust enthalpy split). Those splits are :unmeasured here; a
  higher-fidelity stack-thermal model can register its own contract and
  compose on top. Registered on the shared `cae.solver` dispatch."
  (:require [cae.solver :as cae]))

(defn- pos-num [x]
  (and (number? x) (pos? x)))

(defn stack-heat
  "case: {:stack-kw   electrical stack power (kW), required, > 0
          :eff-lhv    LHV efficiency (fraction), required, 0 < eta < 1
          :coolant-cp-J-kgK  specific heat (J/kg·K), optional
          :coolant-mdot-kg-s mass flow (kg/s), optional
          :coolant-delta-t-K temperature rise (K), optional}
  The coolant group is all-or-none (`:cp` plus exactly one of flow/ΔT);
  the non-supplied side is derived from Q-dot = m-dot·cp·ΔT. Refuses, never
  guesses, when a value is missing or the group is partial/inconsistent."
  [{:keys [stack-kw eff-lhv coolant-cp-J-kgK coolant-mdot-kg-s coolant-delta-t-K]}]
  (when-not (pos-num stack-kw)
    (throw (ex-info "stack-heat: :stack-kw must be a positive number (kW)" {:stack-kw stack-kw})))
  (when-not (and (number? eff-lhv) (< 0 eff-lhv 1))
    (throw (ex-info "stack-heat: :eff-lhv must be in (0,1) — LHV fraction, not percent"
                    {:eff-lhv eff-lhv})))
  (let [q-kw (* stack-kw (- (/ 1.0 eff-lhv) 1.0))
        coolant? (some some? [coolant-cp-J-kgK coolant-mdot-kg-s coolant-delta-t-K])
        supplied (count (filter some? [coolant-mdot-kg-s coolant-delta-t-K]))]
    (when coolant?
      (when-not (pos-num coolant-cp-J-kgK)
        (throw (ex-info "stack-heat: coolant group is all-or-none; :coolant-cp-J-kgK missing or not positive"
                        {:coolant-cp-J-kgK coolant-cp-J-kgK})))
      (when-not (= 1 supplied)
        (throw (ex-info "stack-heat: supply exactly one of :coolant-mdot-kg-s or :coolant-delta-t-K"
                        {:coolant-mdot-kg-s coolant-mdot-kg-s :coolant-delta-t-K coolant-delta-t-K}))))
    (cond-> {:solver :rom-fc-stack-heat
             :stack-kw stack-kw
             :eff-lhv eff-lhv
             ;; exact identity: Q = P(1/eta - 1) given the ROM's own eta
             :waste-heat-kw q-kw
             :coolant {:cp-J-kgK coolant-cp-J-kgK
                       :mdot-kg-s (if coolant-delta-t-K
                                    (/ (* q-kw 1000.0) (* coolant-cp-J-kgK coolant-delta-t-K))
                                    coolant-mdot-kg-s)
                       :delta-t-K (if coolant-mdot-kg-s
                                    (/ (* q-kw 1000.0) (* coolant-cp-J-kgK coolant-mdot-kg-s))
                                    coolant-delta-t-K)}
             :unmeasured {:coolant-fraction "idealized to 1.0 — radiation/conduction/exhaust enthalpy splits not measured"
                          :transient-thermal-mass "steady-state only; stack heat capacity not modeled"}}
      (not coolant?)
      (assoc :coolant {:cp-J-kgK nil :mdot-kg-s nil :delta-t-K nil}
             :note "no coolant group supplied — :waste-heat-kw is the sizing input"))))

(defn from-solver-result
  "Compose with `echem.solver/solve` (or `cae.solver/solve {:solver {:kind :rom-fc}}`):
  pass the ROM result map straight in — `:stack-kW` and `:eff-LHV` are reused
  verbatim, never recomputed. `opts` may carry the coolant group."
  [rom-result opts]
  (stack-heat (merge {:stack-kw (:stack-kW rom-result)
                      :eff-lhv (:eff-LHV rom-result)}
                     opts)))

(defmethod cae/solve :rom-fc-stack-heat [case] (stack-heat case))
