(ns nagare.field
  "Fields as **values** — the data half of the finite-volume model.

  A `volScalarField` (pressure, a scalar transport variable) and a
  `volVectorField` (velocity) are nothing more than one value *per cell*, stored
  as a Clojure vector indexed by the mesh's cell id, plus a **boundaryField**: a
  map from patch name to the boundary condition on that patch. Because the cell
  data is an immutable vector, a whole solution state is a value — you can
  checkpoint a run, diff two correctors, or replay from any step, which is the
  audit-ledger ethos the operators inherit.

  ## Boundary conditions (only what S0/icoFoam needs)
  - **fixedValue** — Dirichlet: the face carries a prescribed value `phi_b`. The
    operator closes the stencil with `phi_b` and folds it into the matrix source.
  - **zeroGradient** — homogeneous Neumann: `dphi/dn = 0`, so the face value is the
    owner-cell value and the face adds *nothing* to a laplacian.
  - **noSlip** — the velocity wall: a `fixedValue` of `(0,0)`.
  - **fixedFluxPressure** — pressure at a wall; for the incompressible cavity it
    behaves as **zeroGradient** for the value lookup (the wall-normal pressure
    gradient balances the body/convective flux, which is zero through a wall).

  These functions are the *only* contract the operators use to reach a boundary:
  `(dirichlet? bc)` and `(boundary-value bc cell-value)`. Everything else about a
  patch is geometry, and lives in `nagare.mesh`."
  (:require [nagare.mesh :as mesh]))

(defn vol-scalar
  "Construct a `volScalarField`: `:values` (vector of doubles, one per cell) and a
  `:boundary` map patch-name -> bc. `init` may be a number or a `(fn [cell-id] ..)`."
  [m init boundary]
  {:mesh m
   :values (let [n (:n-cells m)]
             (if (fn? init)
               (mapv #(double (init %)) (range n))
               (vec (repeat n (double init)))))
   :boundary boundary})

(defn vol-vector
  "Construct a `volVectorField`: `:values` is a vector of `[x y]` per cell. `init`
  may be a `[x y]` pair or a `(fn [cell-id] -> [x y])`."
  [m init boundary]
  {:mesh m
   :values (let [n (:n-cells m)]
             (if (fn? init)
               (mapv #(vec (init %)) (range n))
               (vec (repeat n (vec init)))))
   :boundary boundary})

(defn with-values
  "Return `field` with new `:values` — the pure-update used by the solver loop."
  [field values]
  (assoc field :values values))

;; ---------------------------------------------------------------------------
;; Boundary-condition interpretation (the operator contract)
;; ---------------------------------------------------------------------------

(def ^:private dirichlet-types #{:fixed-value :no-slip})

(defn dirichlet?
  "Does this bc pin the face value (closing the stencil with a known value)?
  `fixedValue`/`noSlip` are Dirichlet; `zeroGradient`/`fixedFluxPressure` are not."
  [bc]
  (contains? dirichlet-types (:type bc)))

(defn bc-value
  "The prescribed face value for a Dirichlet bc (`:value`, or 0/[0 0] for noSlip)."
  [bc]
  (case (:type bc)
    :no-slip (or (:value bc) [0.0 0.0])
    (:value bc)))

(defn boundary-value
  "Face value used by interpolation/gradient: the prescribed value for a Dirichlet
  patch, else the owner-cell value (zeroGradient)."
  [bc cell-value]
  (if (dirichlet? bc) (bc-value bc) cell-value))

(defn patch-bc
  "The bc map for a named patch in `field`'s boundaryField."
  [field nm]
  (get (:boundary field) nm))
