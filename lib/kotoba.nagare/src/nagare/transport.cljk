(ns nagare.transport
  "Steady passive-scalar transport `div(phi,φ) − laplacian(Γ,φ) = 0` with a
  selectable convection scheme.

  - **:upwind** — first-order. Unconditionally bounded (M-matrix) but adds false
    diffusion `~|u|Δx/2`, smearing gradients.
  - **:linear-upwind** — second-order, by **deferred correction**: the implicit
    matrix stays the (stable) upwind one, and the higher-order face value
    `φ_f = φ_U + ∇φ_U·(x_f − x_U)` contributes its *difference from upwind*
    explicitly to the RHS. A few Picard sweeps converge the split; the result
    removes the bulk of the false diffusion while keeping the upwind matrix's
    diagonal dominance. (Boundary faces are left first-order, the usual practice.)
  - **:limited** — bounded second-order (TVD-style). Same deferred correction, but
    the reconstructed face value is clamped into `[min(φ_U,φ_D), max(φ_U,φ_D)]`, a
    local-extremum-diminishing limiter that restores the discrete maximum principle
    (no over/undershoot) while keeping the higher-order accuracy where it is safe."
  (:require [nagare.fvm :as fvm]
            [nagare.field :as field]
            [nagare.linsolve :as ls]))

(defn- cell-gradients
  "Green-Gauss cell gradient [gx gy] per cell (grad-sf is volume-integrated, so
  divide by the cell volume)."
  [m fld]
  (let [[^doubles gx ^doubles gy] (fvm/grad-sf m fld)
        ^doubles vol (:volumes m)
        n (int (:n-cells m))
        cgx (double-array n) cgy (double-array n)]
    (dotimes [c n]
      (aset cgx c (/ (aget gx c) (aget vol c)))
      (aset cgy c (/ (aget gy c) (aget vol c))))
    [cgx cgy]))

(defn solve
  "Solve steady scalar transport on mesh `m` with diffusivity `Γ`, face-flux field
  `phi`, and a scalar field `fld` carrying the boundary conditions. `opts`:
  `{:scheme :upwind|:linear-upwind :picard N :tol t}`. Returns the cell-value
  vector (a Clojure vector of doubles)."
  [m gamma phi fld {:keys [scheme picard tol] :or {scheme :upwind picard 30 tol 1e-11}}]
  (let [A    (fvm/convection-diffusion m gamma phi fld)
        ^doubles base (:source A)
        n    (int (:n-cells m))
        nif  (int (:n-internal m))
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles phi-int (:internal phi)
        centres (:cell-centres m)
        limited? (= scheme :limited)]
    (if (= scheme :upwind)
      (vec (:x (ls/bicgstab A base {:tol 1e-12 :max-iter 4000})))
      (loop [it 0 x (double-array n)]
        (let [[^doubles cgx ^doubles cgy] (cell-gradients m (field/with-values fld (vec x)))
              src (double-array (seq base))
              _ (dotimes [f nif]
                  (let [o (aget own f) p (aget nei f) F (aget phi-int f)
                        u (if (>= F 0.0) o p) d (if (>= F 0.0) p o)
                        cu (nth centres u) cd (nth centres d)
                        ;; corr = ∇φ_U · (x_f − x_U), x_f = ½(x_o + x_p) ⇒ ½(x_D − x_U)
                        corr (+ (* (aget cgx u) 0.5 (- (double (nth cd 0)) (double (nth cu 0))))
                                (* (aget cgy u) 0.5 (- (double (nth cd 1)) (double (nth cu 1)))))
                        ;; :limited clamps the face value into [min,max] of the two cells
                        corr (if limited?
                               (let [pu (aget x u) pd (aget x d)
                                     lo (min pu pd) hi (max pu pd)
                                     fv (max lo (min hi (+ pu corr)))]
                                 (- fv pu))
                               corr)
                        fc (* F corr)]
                    (aset src o (- (aget src o) fc))      ; deferred HO correction
                    (aset src p (+ (aget src p) fc))))
              x' (:x (ls/bicgstab A src {:tol 1e-12 :max-iter 4000 :x0 (double-array x)}))
              delta (areduce x' i s 0.0 (max s (Math/abs (- (aget x' i) (aget ^doubles x i)))))]
          (if (or (>= it picard) (< delta tol))
            (vec x')
            (recur (inc it) x')))))))
