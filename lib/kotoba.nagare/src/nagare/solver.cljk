(ns nagare.solver
  "PISO — transient incompressible pressure-velocity coupling (the icoFoam loop).

  The incompressible Navier-Stokes equations couple momentum and a *constraint*
  (continuity `nabla.U = 0`) rather than an evolution equation for pressure. PISO
  (Pressure-Implicit with Splitting of Operators) resolves that coupling within a
  time step by a predictor + two-or-more corrector passes, never iterating
  unboundedly — one `advance` call is one bounded simulation, matching the actor
  discipline.

  ## One time step
  1. **Momentum predictor.** Assemble `M = ddt + div(phi,U) - laplacian(nu,U)` and
     solve `M U* = source - grad(p)` (BiCGStab, per component) for a provisional
     velocity that does not yet satisfy continuity.
  2. **PISO correctors** (>= 2):
     - `rAU = V/diag(M)`; `HbyA = (source - off-diagonal.U)/diag(M)` — the velocity
       reconstructed from momentum *without* the pressure gradient.
     - `phiHbyA` = `HbyA` interpolated to faces and dotted with `Sf` (impermeable
       walls contribute zero) — the Rhie-Chow predicted face flux.
     - Solve the pressure-Poisson `laplacian(rAU,p) = div(phiHbyA)` (PCG, SPD).
     - **Correct** the face flux `phi = phiHbyA - pEqn.flux()` (now discretely
       divergence-free) and the velocity `U = HbyA - rAU grad(p)`.

  The second (and later) corrector re-evaluates `HbyA` with the freshly corrected
  velocity, which is what lets PISO converge the split within the step without
  outer iterations. Constant `nu`, collocated arrangement, backward-Euler time."
  (:require [nagare.field :as field]
            [nagare.fvm :as fvm]
            [nagare.linsolve :as ls]))

(defn- off-diagonal-dot
  "For each cell P, `Sum_N a_PN x_N` over the momentum off-diagonals — owner rows
  pick up `upper[f]*x[neighbour]`, neighbour rows `lower[f]*x[owner]`."
  [M xs]
  (let [n (int (:n M))
        ^ints own (:owner M) ^ints nei (:neighbour M)
        ^doubles up (:upper M) ^doubles lo (:lower M)
        nf (int (alength up))
        out (double-array n)]
    (dotimes [f nf]
      (let [o (aget own f) p (aget nei f)]
        (aset out o (+ (aget out o) (* (aget up f) (double (xs p)))))
        (aset out p (+ (aget out p) (* (aget lo f) (double (xs o)))))))
    out))

(defn- hbya
  "HbyA component = (source - off-diagonal.U)/diag, per component, as `double[]`."
  [M ^doubles src component-fn]
  (let [n (int (:n M))
        ^doubles diag (:diag M)
        off (off-diagonal-dot M component-fn)
        out (double-array n)]
    (dotimes [c n]
      (aset out c (/ (- (aget src c) (aget off c)) (aget diag c))))
    out))

(defn- phi-hbya
  "Predicted face flux from interpolated HbyA dotted with Sf. Internal faces use
  linear interpolation; boundary faces use the prescribed wall flux `U_b.Sf`
  (zero for impermeable cavity walls)."
  [m ^doubles hx ^doubles hy U]
  (let [nif (int (:n-internal m))
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles sfx (:if-sfx m) ^doubles sfy (:if-sfy m)
        ^doubles fx (:if-fx m)
        internal (double-array nif)]
    (dotimes [f nif]
      (let [o (aget own f) p (aget nei f) w (aget fx f)
            hfx (+ (* w (aget hx o)) (* (- 1.0 w) (aget hx p)))
            hfy (+ (* w (aget hy o)) (* (- 1.0 w) (aget hy p)))]
        (aset internal f (+ (* hfx (aget sfx f)) (* hfy (aget sfy f))))))
    {:internal internal
     :patches (into {}
                    (for [pt (:patches m)]
                      (let [bc (field/patch-bc U (:name pt))
                            np (int (:n pt))
                            ^doubles psfx (:sfx pt) ^doubles psfy (:sfy pt)
                            arr (double-array np)]
                        (when (field/dirichlet? bc)
                          (let [vb (field/bc-value bc)
                                vx (double (nth vb 0)) vy (double (nth vb 1))]
                            (dotimes [k np]
                              (aset arr k (+ (* vx (aget psfx k)) (* vy (aget psfy k)))))))
                        [(:name pt) arr])))}))

(defn- zero-flux
  "An all-zero face-flux field for the very first time step (`phi^0 = 0`)."
  [m]
  {:internal (double-array (:n-internal m))
   :patches (into {} (for [pt (:patches m)] [(:name pt) (double-array (:n pt))]))})

(defn- component-field
  "A scalar field of velocity component `k` (0=u, 1=v), with each Dirichlet
  patch's scalar bc set to that component of the vector wall value. Lets the
  scalar `grad-sf` recover the per-component gradient for the div correction."
  [U k]
  (assoc U
         :values (mapv #(double (nth % k)) (:values U))
         :boundary (into {} (for [[nm bc] (:boundary U)]
                              [nm (if (field/dirichlet? bc)
                                    {:type :fixed-value :value (double (nth (field/bc-value bc) k))}
                                    bc)]))))

(defn- div-ho-correction
  "Deferred linear-upwind correction `[dx dy]` (per cell, per component) for
  `div(phi,U)`: the convected face velocity is raised from the upwind cell value
  to `U_U + ∇U_U·(x_f − x_U)`, and the extra flux `F·corr` is moved to the RHS
  (`−F·corr` to owner, `+F·corr` to neighbour). Lagged gradient (explicit)."
  [m phi U]
  (let [n (int (:n-cells m))
        nif (int (:n-internal m))
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles phi-int (:internal phi)
        centres (:cell-centres m)
        ^doubles vol (:volumes m)
        grads (mapv (fn [k]
                      (let [[^doubles gx ^doubles gy] (fvm/grad-sf m (component-field U k))]
                        [gx gy])) [0 1])
        dx (double-array n) dy (double-array n)
        out [dx dy]]
    (dotimes [f nif]
      (let [o (aget own f) p (aget nei f) F (aget phi-int f)
            u (if (>= F 0.0) o p) d (if (>= F 0.0) p o)
            cu (nth centres u) cd (nth centres d)
            hx (* 0.5 (- (double (nth cd 0)) (double (nth cu 0))))
            hy (* 0.5 (- (double (nth cd 1)) (double (nth cu 1))))]
        (dotimes [k 2]
          (let [[^doubles gx ^doubles gy] (nth grads k)
                ;; cell gradient = volume-integrated grad-sf / V
                corr (+ (* (/ (aget gx u) (aget vol u)) hx)
                        (* (/ (aget gy u) (aget vol u)) hy))
                fc (* F corr)
                ^doubles arr (nth out k)]
            (aset arr o (- (aget arr o) fc))
            (aset arr p (+ (aget arr p) fc))))))
    out))

(defn step
  "Advance the state `{:U :p :phi}` by one PISO time step. `params` is
  `{:nu :dt :n-correctors :ref-cell :p-tol :u-tol :max-iter :div-scheme}`.
  `:div-scheme` is `:upwind` (default) or `:linear-upwind` (deferred correction)."
  [m {:keys [nu dt n-correctors ref-cell p-tol u-tol max-iter div-scheme]
      :or {n-correctors 2 ref-cell 0 p-tol 1e-7 u-tol 1e-6 max-iter 500 div-scheme :upwind}
      :as params}
   {:keys [U p phi] :as state}]
  (let [^doubles vol (:volumes m)
        n (int (:n-cells m))
        phi (or phi (zero-flux m))
        u-old U
        ;; (1) momentum predictor
        M (fvm/momentum m params U phi u-old)
        ^doubles diag (:diag M)
        ^doubles sx (:sx M) ^doubles sy (:sy M)
        [gpx gpy] (fvm/grad-sf m p)
        [^doubles cdx ^doubles cdy] (if (= div-scheme :linear-upwind)
                                      (div-ho-correction m phi U)
                                      [(double-array n) (double-array n)])
        rhsx (double-array n) rhsy (double-array n)
        _ (dotimes [c n]
            (aset rhsx c (+ (- (aget sx c) (aget ^doubles gpx c)) (aget cdx c)))
            (aset rhsy c (+ (- (aget sy c) (aget ^doubles gpy c)) (aget cdy c))))
        u0 (mapv #(double (nth % 0)) (:values U))
        v0 (mapv #(double (nth % 1)) (:values U))
        us (:x (ls/bicgstab M rhsx {:max-iter max-iter :tol u-tol :x0 (double-array u0)}))
        vs (:x (ls/bicgstab M rhsy {:max-iter max-iter :tol u-tol :x0 (double-array v0)}))
        Uvals (mapv (fn [i] [(aget ^doubles us i) (aget ^doubles vs i)]) (range n))
        ;; rAU = V / diag
        rAU (double-array n)
        _ (dotimes [c n] (aset rAU c (/ (aget vol c) (aget diag c))))]
    ;; (2) PISO correctors
    (loop [corr 0
           U* (field/with-values U Uvals)
           p* p
           phi* phi]
      (if (>= corr n-correctors)
        {:U U* :p p* :phi phi*}
        (let [uxs (mapv #(double (nth % 0)) (:values U*))
              uys (mapv #(double (nth % 1)) (:values U*))
              hx (hbya M sx uxs)
              hy (hbya M sy uys)
              phiHbyA (phi-hbya m hx hy U*)
              pEqn (fvm/pressure-eqn m rAU phiHbyA p* ref-cell)
              p-new (:x (ls/pcg pEqn (:source pEqn)
                                {:max-iter max-iter :tol p-tol
                                 :x0 (double-array (mapv double (:values p*)))}))
              p-field (field/with-values p* (vec p-new))
              ;; flux correction: phi = phiHbyA - pEqn.flux()
              corr-flux (fvm/face-flux-correction m rAU p-field)
              ^doubles ph-int (:internal phiHbyA)
              new-int (double-array (:n-internal m))
              _ (dotimes [f (:n-internal m)]
                  (aset new-int f (- (aget ph-int f) (aget ^doubles corr-flux f))))
              phi-new {:internal new-int :patches (:patches phiHbyA)}
              ;; velocity correction: U = HbyA - rAU * grad(p)/V
              [gx gy] (fvm/grad-sf m p-field)
              Unew (mapv (fn [c]
                           [(- (aget ^doubles hx c) (* (aget rAU c) (/ (aget ^doubles gx c) (aget vol c))))
                            (- (aget ^doubles hy c) (* (aget rAU c) (/ (aget ^doubles gy c) (aget vol c))))])
                         (range n))]
          (recur (inc corr)
                 (field/with-values U* Unew)
                 p-field
                 phi-new))))))

(defn advance
  "Run PISO for up to `:steps` time steps (or until the max velocity change between
  steps drops below `:steady-tol`). Returns the final state plus `:steps-run` and
  the per-step residual history. Pure: state in, state out."
  [m params init {:keys [steps steady-tol] :or {steps 1000 steady-tol 1e-5}}]
  (loop [k 0 st init hist []]
    (if (>= k steps)
      (assoc st :steps-run k :history hist)
      (let [st' (step m params st)
            delta (reduce max 0.0
                          (map (fn [a b]
                                 (max (Math/abs (- (double (nth a 0)) (double (nth b 0))))
                                      (Math/abs (- (double (nth a 1)) (double (nth b 1))))))
                               (:values (:U st')) (:values (:U st))))]
        (if (< delta steady-tol)
          (assoc st' :steps-run (inc k) :history (conj hist delta) :converged true)
          (recur (inc k) st' (conj hist delta)))))))

;; ---------------------------------------------------------------------------
;; SIMPLE — steady incompressible coupling (the simpleFoam loop)
;; ---------------------------------------------------------------------------

(defn simple-step
  "One steady SIMPLE outer iteration. Unlike PISO there is no time derivative — a
  fixed point of the steady momentum + continuity is reached by UNDER-RELAXATION
  instead of a Δt:

  1. Assemble the steady momentum matrix (a huge `dt` annihilates the `ddt` term),
     then **implicitly under-relax** it: A_P ← A_P/α_U with the matching
     `((1−α_U)/α_U)·A_P·U_P^old` added to the source. That relaxed diagonal both
     stabilizes the solve and defines `rAU`.
  2. Solve the momentum predictor `M' U* = source' − ∇p`.
  3. One corrector: pressure-Poisson `laplacian(rAU,p)=div(phiHbyA)`, correct the
     face flux and the velocity with the **unrelaxed** new pressure (simpleFoam
     order), then **explicitly under-relax** the stored pressure
     `p ← p^old + α_p (p* − p^old)` for the next iteration's momentum/∇p.

  `params` adds `{:alpha-u :alpha-p}` to the usual `{:nu :ref-cell :p-tol :u-tol
  :max-iter}`. Returns the next `{:U :p :phi}`."
  [m {:keys [alpha-u alpha-p ref-cell p-tol u-tol max-iter]
      :or {alpha-u 0.7 alpha-p 0.3 ref-cell 0 p-tol 1e-7 u-tol 1e-6 max-iter 400}
      :as params}
   {:keys [U p phi]}]
  (let [^doubles vol (:volumes m)
        n (int (:n-cells m))
        phi (or phi (zero-flux m))
        M (fvm/momentum m (assoc params :dt 1.0e30) U phi U)   ; steady: ddt → 0
        ^doubles diag0 (:diag M)
        ^doubles sx (:sx M) ^doubles sy (:sy M)
        u0 (mapv #(double (nth % 0)) (:values U))
        v0 (mapv #(double (nth % 1)) (:values U))
        r  (/ (- 1.0 alpha-u) alpha-u)
        diag (double-array n) rsx (double-array n) rsy (double-array n)
        _ (dotimes [c n]
            (aset diag c (/ (aget diag0 c) alpha-u))
            (aset rsx c (+ (aget sx c) (* r (aget diag0 c) (nth u0 c))))
            (aset rsy c (+ (aget sy c) (* r (aget diag0 c) (nth v0 c)))))
        Mr (assoc M :diag diag :sx rsx :sy rsy)
        [gpx gpy] (fvm/grad-sf m p)
        rhsx (double-array n) rhsy (double-array n)
        _ (dotimes [c n]
            (aset rhsx c (- (aget rsx c) (aget ^doubles gpx c)))
            (aset rhsy c (- (aget rsy c) (aget ^doubles gpy c))))
        us (:x (ls/bicgstab Mr rhsx {:max-iter max-iter :tol u-tol :x0 (double-array u0)}))
        vs (:x (ls/bicgstab Mr rhsy {:max-iter max-iter :tol u-tol :x0 (double-array v0)}))
        Uvals (mapv (fn [i] [(aget ^doubles us i) (aget ^doubles vs i)]) (range n))
        U* (field/with-values U Uvals)
        rAU (double-array n)
        _ (dotimes [c n] (aset rAU c (/ (aget vol c) (aget diag c))))
        uxs (mapv #(double (nth % 0)) (:values U*))
        uys (mapv #(double (nth % 1)) (:values U*))
        hx (hbya Mr rsx uxs)
        hy (hbya Mr rsy uys)
        phiHbyA (phi-hbya m hx hy U*)
        pEqn (fvm/pressure-eqn m rAU phiHbyA p ref-cell)
        p-star (:x (ls/pcg pEqn (:source pEqn)
                           {:max-iter max-iter :tol p-tol
                            :x0 (double-array (mapv double (:values p)))}))
        p-star-field (field/with-values p (vec p-star))
        ;; correct flux & velocity with the UNRELAXED new pressure
        corr-flux (fvm/face-flux-correction m rAU p-star-field)
        ^doubles ph-int (:internal phiHbyA)
        new-int (double-array (:n-internal m))
        _ (dotimes [f (:n-internal m)]
            (aset new-int f (- (aget ph-int f) (aget ^doubles corr-flux f))))
        phi-new {:internal new-int :patches (:patches phiHbyA)}
        [gx gy] (fvm/grad-sf m p-star-field)
        Unew (mapv (fn [c]
                     [(- (aget ^doubles hx c) (* (aget rAU c) (/ (aget ^doubles gx c) (aget vol c))))
                      (- (aget ^doubles hy c) (* (aget rAU c) (/ (aget ^doubles gy c) (aget vol c))))])
                   (range n))
        ;; explicitly under-relax the STORED pressure for the next iteration
        p-relaxed (mapv (fn [po ps] (+ po (* alpha-p (- ps po)))) (:values p) p-star)]
    {:U (field/with-values U* Unew)
     :p (field/with-values p (vec p-relaxed))
     :phi phi-new}))

(defn advance-simple
  "Iterate SIMPLE to a steady state — up to `:steps` outer iterations or until the
  max velocity change drops below `:steady-tol`. Same return shape as `advance`."
  [m params init {:keys [steps steady-tol] :or {steps 2000 steady-tol 1e-5}}]
  (loop [k 0 st init hist []]
    (if (>= k steps)
      (assoc st :steps-run k :history hist)
      (let [st' (simple-step m params st)
            delta (reduce max 0.0
                          (map (fn [a b]
                                 (max (Math/abs (- (double (nth a 0)) (double (nth b 0))))
                                      (Math/abs (- (double (nth a 1)) (double (nth b 1))))))
                               (:values (:U st')) (:values (:U st))))]
        (if (< delta steady-tol)
          (assoc st' :steps-run (inc k) :history (conj hist delta) :converged true)
          (recur (inc k) st' (conj hist delta)))))))
