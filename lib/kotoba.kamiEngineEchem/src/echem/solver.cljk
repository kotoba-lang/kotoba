(ns echem.solver
  "Reduced-order PEM fuel-cell solver (:rom-fc) — a single-cell polarization
  curve V(i) = E0 − activation − ohmic − concentration, summed over the stack.
  Cell voltage sets LHV efficiency (η = V / 1.254 V thermoneutral), and the
  operating current density sets stack power. This is the right 'combustion'
  analog for an FCEV: electrochemistry, not chemistry. Turns the design's fixed
  stack-efficiency assumption into a computed η → real H2 consumption.

  A detailed kami-echem (channel CFD + electrochem) registers :pemfc-cfd on the
  same cae-solver contract for higher fidelity.

  Operating-point contract (`curve` / `solve-at-power`): the downstream vehicle
  sizing (kami-engine-vehicle-designer :cae-probe) needs the efficiency *at the
  stack power the vehicle actually demands*, not at a fixed default current
  density. `solve-at-power` inverts the polarization curve — given a required
  stack power it finds the operating current density by bisection (the power
  curve i·V(i) is single-peaked on (0, i-lim)) and returns the Faraday-law H2
  consumption at that point. Only physical constants appear here (Faraday
  constant, H2 molar mass, thermoneutral voltage); no empirical performance
  constants beyond the caller-supplied polarization parameters."
  (:require [datom.core :as d]
            [cae.solver :as cae]))

(def ^:const V-thermoneutral-LHV 1.254)   ; V; η_LHV = V_cell / 1.254
(def ^:const faraday-const 96485.332)     ; C/mol (exact physical constant)
(def ^:const molar-mass-h2 2.016e-3)      ; kg/mol H2

(defn- cell-power-w
  "Stack power W at current density i (A/cm²) for the given case parameters."
  [{:keys [area-cm2 cells] :or {area-cm2 300 cells 370}} i v-cell]
  (* v-cell i area-cm2 cells))

(defn- v-cell-at
  "Cell voltage V at current density i for the given polarization parameters."
  [{:keys [pt-loading
           E0 tafel-b i0 R-ohm i-lim conc-c]
    :or {pt-loading 0.2
         E0 1.00 tafel-b 0.045 i0 1.0e-2 R-ohm 0.08 i-lim 2.0 conc-c 0.04}}
   i]
  (let [i0eff  (* i0 (/ pt-loading 0.2))               ; exchange current ∝ Pt
        act    (* tafel-b (Math/log (/ i i0eff)))      ; activation overpotential
        ohm    (* i R-ohm)                             ; ohmic (R in Ω·cm²)
        conc   (if (< i i-lim) (* (- conc-c) (Math/log (- 1.0 (/ i i-lim)))) 0.5)]
    ;; clamp at the reversible voltage: Tafel extrapolation below i0 would
    ;; otherwise push V above E0, which is unphysical (OCV ≈ E0 ceiling)
    (max 0.0 (min E0 (- E0 act ohm conc)))))

(defn- solve-case
  "Full solve at an explicit current density i. Same outputs as `solve`."
  [case i]
  (let [{:keys [cells area-cm2]} case
        v-cell (v-cell-at case i)
        eff    (/ v-cell V-thermoneutral-LHV)
        p-w    (cell-power-w case i v-cell)
        h2-gps (* 1000.0
                  (/ (* i (or area-cm2 300) (or cells 370) molar-mass-h2)
                     (* 2.0 faraday-const)))]         ; Faraday: I/(2F) mol/s → g/s
    {:v-cell v-cell :eff-LHV eff :stack-kW (/ p-w 1000.0)
     :h2-g-per-s h2-gps
     :cells (or cells 370) :i-density i :T-K (:T-K case 353)
     :overpotentials (let [i0eff (* (:i0 case 1.0e-2) (/ (:pt-loading case 0.2) 0.2))]
                       {:act (* (:tafel-b case 0.045) (Math/log (/ i i0eff)))
                        :ohm (* i (:R-ohm case 0.08))
                        :conc (if (< i (:i-lim case 2.0))
                                (* (- (:conc-c case 0.04))
                                   (Math/log (- 1.0 (/ i (:i-lim case 2.0)))))
                                0.5)})
     :solver :rom-fc}))

(defn solve
  "case: {:cells :area-cm2 :i-density(A/cm²) :T-K :pt-loading
          :E0 :tafel-b :i0 :R-ohm :i-lim :conc-c}"
  [{:keys [cells area-cm2 i-density T-K pt-loading
           E0 tafel-b i0 R-ohm i-lim conc-c]
    :or {cells 370 area-cm2 300 i-density 1.2 T-K 353 pt-loading 0.2
         E0 1.00 tafel-b 0.045 i0 1.0e-2 R-ohm 0.08 i-lim 2.0 conc-c 0.04}}]
  (solve-case {:cells cells :area-cm2 area-cm2 :T-K T-K :pt-loading pt-loading
               :E0 E0 :tafel-b tafel-b :i0 i0 :R-ohm R-ohm
               :i-lim i-lim :conc-c conc-c}
              i-density))

(defn curve
  "Reproducible polarization-curve sweep: samples `n` current densities over
  (ε·i-lim, i-lim) and returns [{:i-density :v-cell :stack-kW :eff-LHV}] sorted
  by i-density. The sweep is the acceptance surface for any operating point
  solved against it."
  ([case] (curve case 40))
  ([case n]
   (let [{:keys [i-lim] :or {i-lim 2.0}} case
         eps 1.0e-6
         step (/ (* i-lim (- 1.0 (* 2.0 eps))) (dec n))]
     (vec
      (for [k (range n)]
        (let [i (+ (* eps i-lim) (* k step))
              r (solve-case case i)]
          (select-keys r [:i-density :v-cell :stack-kW :eff-LHV])))))))

(defn solve-at-power
  "Invert the polarization curve: given a required stack power `p-kw`, find the
  lowest current density that delivers it (i·V(i) is single-peaked on (0, i-lim),
  so below the peak the power curve is strictly monotone and the inversion is
  unique). Returns the full operating point (see `solve`) plus
  :p-stack-kW-target, :feasible, and :peak-kW (the maximum achievable stack
  power for this case). An unreachable target returns :feasible false and the
  peak point — never a fabricated solution."
  [case p-kw]
  (let [n 400
        pts (curve case n)
        peak (apply max-key :stack-kW pts)
        peak-kw (:stack-kW peak)]
    (if (> p-kw peak-kw)
      (assoc (solve-case case (:i-density peak))
             :p-stack-kW-target p-kw :feasible false :peak-kW peak-kw)
      (let [eps 1.0e-6
            i-lo (* eps (:i-lim case 2.0))
            i-hi (:i-density peak)
            i*   (loop [lo i-lo hi i-hi]
                   (let [mid (/ (+ lo hi) 2.0)
                         pmid (:stack-kW (solve-case case mid))]
                     (cond
                       (< (/ (- hi lo) hi) 1.0e-9) mid
                       (< pmid p-kw) (recur mid hi)
                       :else (recur lo mid))))
            r (solve-case case i*)]
        (assoc r
               :p-stack-kW-target p-kw :feasible true :peak-kW peak-kw)))))

(def ^:const h2-lhv-j-per-kg
  "LHV energy content of H2 implied by the thermoneutral voltage:
  V_tn · 2F / M_H2 ≈ 1.20e8 J/kg. Derived from the constants above, not an
  independent empirical number — this is the internal-consistency anchor for
  the H2 consumption contract."
  (/ (* V-thermoneutral-LHV 2.0 faraday-const) molar-mass-h2))

(defmethod cae/solve :rom-fc [case] (solve case))

(defn run [case]
  (let [r   (solve case)
        cid (or (:case/id case) "fc-0")
        ent (d/entity "echem" :FuelCellRun cid
                      {:cells   (:cells r)
                       :vCellMv (Math/round (* 1000.0 (:v-cell r)))
                       :effPct  (Math/round (* 100.0 (:eff-LHV r)))
                       :stackKW (Math/round (double (:stack-kW r)))})
        led (d/log [ent])]
    (assoc r :datoms (:datoms led) :datom-count (:count led))))
