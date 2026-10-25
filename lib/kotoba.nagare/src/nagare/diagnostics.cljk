(ns nagare.diagnostics
  "Stability / accuracy diagnostics computed from a face-flux field `phi`.

  The two dimensionless numbers that decide whether a CFD run is well posed:

  - **Courant number** `Co = ½ (Δt/V_P) Σ_f |phi_f|` (the OpenFOAM cell form). It
    measures how many cells a parcel crosses per step; an explicit/transient run
    needs `Co ≲ 1`, and PISO accuracy degrades as it grows. For a uniform field
    `U=(u,0)` on a `Δx×Δy` mesh this reduces to `u Δt/Δx`.

  - **Cell Peclet number** `Pe = |phi_f| |d| / (ν |Sf|)` per face — the convective/
    diffusive flux ratio `|u| Δx/ν`. Above `Pe ≈ 2` central differencing goes
    unbounded (the checkerboard the cavity would show), which is exactly why the
    convection term defaults to upwind.

  Pure functions of the mesh geometry and a flux field — no solver state, so they
  can monitor any step of a run." )

(defn courant
  "Per-cell Courant number from a face-flux field `phi` and step `dt`. Sums
  `|phi_f|` over each cell's internal faces (OpenFOAM ½ factor). Returns a
  `double[]` indexed by cell."
  [m phi dt]
  (let [n (int (:n-cells m))
        acc (double-array n)
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles ifl (:internal phi)
        ^doubles vol (:volumes m)]
    (dotimes [f (int (:n-internal m))]
      (let [o (aget own f) p (aget nei f) a (Math/abs (aget ifl f))]
        (aset acc o (+ (aget acc o) a))
        (aset acc p (+ (aget acc p) a))))
    (let [out (double-array n)]
      (dotimes [c n] (aset out c (* 0.5 (/ (double dt) (aget vol c)) (aget acc c))))
      out)))

(defn max-courant
  "The largest cell Courant number — the single number that gates an explicit step."
  [m phi dt]
  (reduce max 0.0 (courant m phi dt)))

(defn cell-peclet
  "Per-cell maximum face Peclet `|phi_f| |d| / (ν |Sf|)` over the cell's internal
  faces. Returns a `double[]` indexed by cell."
  [m phi nu]
  (let [n (int (:n-cells m))
        out (double-array n)
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles ifl (:internal phi)
        ^doubles area (:if-area m) ^doubles dmag (:if-dmag m)]
    (dotimes [f (int (:n-internal m))]
      (let [o (aget own f) p (aget nei f)
            pe (/ (* (Math/abs (aget ifl f)) (aget dmag f)) (* (double nu) (aget area f)))]
        (when (> pe (aget out o)) (aset out o pe))
        (when (> pe (aget out p)) (aset out p pe))))
    out))

(defn max-peclet
  "The largest cell Peclet number — above ~2 a non-upwind convection scheme
  would go unbounded."
  [m phi nu]
  (reduce max 0.0 (cell-peclet m phi nu)))
