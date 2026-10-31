(ns pack.solver
  "Reduced-order lithium battery PACK solver (:rom-pack) — cell specific energy
  scaled to pack level, then derated for the discharge RATE the aircraft
  actually pulls. Registers on the same cae-solver contract as the rotor, motor
  and aero solvers.

  Why a solver and not a constant. `vdesign.powertrain` carries a fixed
  175 Wh/kg pack figure, which is right for a car: an EV cruises near 0.5C and
  the rate term is negligible. A multirotor hovers at 3-6C and pulls 10C or more
  in a climb, where two rate effects stop being negligible:

    energy  — Peukert: delivered capacity falls as (1/C)^(k-1)
    power   — internal resistance: pack voltage sags roughly linearly in C

  Treat those as zero and a drone's endurance comes out optimistic by 5-15%,
  which is the difference between a design that flies its mission and one that
  lands early.

  The inverse has a closed form, which is why the sizing does not iterate:

      E_usable = E_nom * DoD * (E_nom/P)^(k-1)
               = DoD * E_nom^k / P^(k-1)
    =>  E_nom  = (E_required * P^(k-1) / DoD)^(1/k)

  Scope: energy and rate. NOT temperature, NOT cycle ageing, NOT state of
  health, NOT cell balancing, NOT thermal runaway. A pack at -10 C or at 500
  cycles is a different pack and this solver does not know it. The chemistry
  table below is representative catalogue data, not measurement."
  (:require [datom.core :as d]
            [cae.solver :as cae]))

;; Cell-level figures. `:cell-Wh-kg` is gravimetric energy of the bare cell;
;; `:max-C` its continuous discharge rating; `:peukert` the exponent k in
;; (1/C)^(k-1); `:r-frac-per-C` the fraction of nominal voltage lost per C of
;; load. High-rate chemistries trade energy for power — that trade is the whole
;; reason this is a table and not one number.
(def chemistries
  {:lipo-highrate {:cell-Wh-kg 180.0 :max-C 45.0 :peukert 1.03 :r-frac-per-C 0.0080}
   :li-ion-power  {:cell-Wh-kg 200.0 :max-C 15.0 :peukert 1.04 :r-frac-per-C 0.0060}
   :li-ion-energy {:cell-Wh-kg 260.0 :max-C  5.0 :peukert 1.06 :r-frac-per-C 0.0140}
   :lfp           {:cell-Wh-kg 160.0 :max-C 10.0 :peukert 1.05 :r-frac-per-C 0.0090}
   :si-anode      {:cell-Wh-kg 400.0 :max-C  5.0 :peukert 1.08 :r-frac-per-C 0.0180}})

(defn- positive!
  [m k]
  (let [v (get m k)]
    (when-not (and (number? v) (pos? v))
      (throw (ex-info "pack solve needs a positive value" {:key k :value v})))
    (double v)))

(defn- chemistry!
  "Resolve the chemistry, refusing an unknown name instead of quietly falling
  back to a default — a silent default here is a wrong pack mass that looks
  like a right one."
  [k]
  (or (get chemistries k)
      (throw (ex-info "unknown cell chemistry"
                      {:chemistry k :known (vec (sort (keys chemistries)))}))))

(defn- check-fractions!
  [{:keys [dod cell-mass-frac]}]
  (when-not (and (number? dod) (< 0.0 dod) (<= dod 1.0))
    (throw (ex-info "depth of discharge must be in (0, 1]" {:key :dod :value dod})))
  (when-not (and (number? cell-mass-frac) (< 0.0 cell-mass-frac) (<= cell-mass-frac 1.0))
    (throw (ex-info "cell mass fraction must be in (0, 1]"
                    {:key :cell-mass-frac :value cell-mass-frac}))))

(defn pack-Wh-kg
  "Pack-level gravimetric energy: cell energy times the share of pack mass that
  is actually cell. The remainder is BMS, wiring, connectors and case."
  [{:keys [chemistry cell-mass-frac] :or {chemistry :lipo-highrate cell-mass-frac 0.82}}]
  (* (:cell-Wh-kg (chemistry! chemistry)) cell-mass-frac))

(defn solve
  "FORWARD: what does this pack deliver at this load?

  case: {:pack-mass-kg :p-elec-W :chemistry :dod :cell-mass-frac}"
  [{:keys [chemistry dod cell-mass-frac]
    :or {chemistry :lipo-highrate dod 0.85 cell-mass-frac 0.82}
    :as case}]
  (let [{:keys [max-C peukert r-frac-per-C]} (chemistry! chemistry)
        _      (check-fractions! {:dod dod :cell-mass-frac cell-mass-frac})
        mass   (positive! case :pack-mass-kg)
        p      (positive! case :p-elec-W)
        wh-kg  (pack-Wh-kg {:chemistry chemistry :cell-mass-frac cell-mass-frac})
        e-nom  (* mass wh-kg)                       ; Wh
        c-rate (/ p e-nom)                          ; 1/h
        rate-frac (Math/pow (/ 1.0 c-rate) (- peukert 1.0))
        e-use  (* e-nom dod rate-frac)              ; Wh actually available
        hours  (/ e-use p)
        sag    (* r-frac-per-C c-rate)]
    {:pack-mass-kg mass :p-elec-W p :chemistry chemistry
     :pack-Wh-per-kg wh-kg :nominal-Wh e-nom :usable-Wh e-use
     :c-rate c-rate :max-C max-C
     :over-rate? (> c-rate max-C)
     :rate-capacity-frac rate-frac :peukert peukert
     :v-under-load-frac (max 0.0 (- 1.0 sag)) :sag-frac sag
     :endurance-h hours :endurance-min (* 60.0 hours)
     :dod dod
     :solver :rom-pack}))

(defn size-for-endurance
  "INVERSE sizing: the pack that sustains `:p-elec-W` for `:endurance-min`.

  Closed form — E_nom = (E_required * P^(k-1) / DoD)^(1/k) — because the rate
  derating depends on the pack size that is being solved for. Iterating this
  would converge to the same number more slowly and less obviously."
  [{:keys [chemistry dod cell-mass-frac]
    :or {chemistry :lipo-highrate dod 0.85 cell-mass-frac 0.82}
    :as case}]
  (let [{:keys [peukert]} (chemistry! chemistry)
        _      (check-fractions! {:dod dod :cell-mass-frac cell-mass-frac})
        p      (positive! case :p-elec-W)
        mins   (positive! case :endurance-min)
        hours  (/ mins 60.0)
        e-req  (* p hours)                                   ; Wh that must come out
        e-nom  (Math/pow (/ (* e-req (Math/pow p (- peukert 1.0))) dod)
                         (/ 1.0 peukert))
        wh-kg  (pack-Wh-kg {:chemistry chemistry :cell-mass-frac cell-mass-frac})
        mass   (/ e-nom wh-kg)]
    (assoc (solve (assoc case :pack-mass-kg mass :chemistry chemistry
                         :dod dod :cell-mass-frac cell-mass-frac))
           :sized-for {:p-elec-W p :endurance-min mins :required-Wh e-req})))

(defmethod cae/solve :rom-pack [case]
  (if (:endurance-min case) (size-for-endurance case) (solve case)))

(defn run
  [case]
  (let [r   (cae/solve (assoc-in case [:solver :kind] :rom-pack))
        cid (or (:case/id case) "pack-0")
        ent (d/entity "pack" :PackRun cid
                      {:chemistry (name (:chemistry r))
                       :massG     (Math/round (* 1000.0 (:pack-mass-kg r)))
                       :nominalWh (Math/round (double (:nominal-Wh r)))
                       :usableWh  (Math/round (double (:usable-Wh r)))
                       :cRate     (Math/round (* 100.0 (:c-rate r)))
                       :endurMin  (Math/round (* 10.0 (:endurance-min r)))
                       :sagPct    (Math/round (* 100.0 (:sag-frac r)))
                       :overRate  (if (:over-rate? r) 1 0)})
        led (d/log [ent])]
    (assoc r :datoms (:datoms led) :datom-count (:count led))))
