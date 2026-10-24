(ns nagare.fvm
  "Discretization — turning differential operators into a sparse **fvMatrix**.

  Integrate a conservation law over a control volume and apply the divergence
  theorem: the volume integral of any `div`/`laplacian` collapses into a **sum of
  face fluxes**. Each operator here assembles the same plain-data sparse matrix

      {:n N :diag d[N] :upper u[Fi] :lower l[Fi] :owner :neighbour :source b[N]}

  where `upper[f]`/`lower[f]` are the owner-row and neighbour-row off-diagonals for
  internal face `f`, and `:source` is the explicit right-hand side (it already
  absorbs the Dirichlet boundary contributions). `:owner`/`:neighbour` are carried
  through verbatim from the mesh so the matrix is self-contained for `linsolve`.

  ## Sign convention (read this once)
  We assemble every operator in the **positive-diagonal** convention: each operator
  contributes a non-negative diagonal and non-positive off-diagonals, so the
  assembled matrices are diagonally dominant (and the Laplacian is SPD). Concretely
  the diffusion term is `-laplacian(gamma, .)` = the discrete *negative* Laplacian.
  To solve `nabla^2 phi = f` one therefore solves `L phi = -f V + (Dirichlet src)`.

  ## The operators
  - **laplacian** `Sum_f gamma_f |Sf|/|d| (phi_P - phi_N)` — diffusion; symmetric.
  - **div** (convection) with **upwind** interpolation given face fluxes `phi_f`:
    `phi_f = phi_P` if the flux leaves the owner, else `phi_N`. First-order, bounded,
    diagonally dominant — the right default for a coarse verification mesh.
  - **ddt** (backward-Euler) `V_P/dt` onto the diagonal, `V_P/dt phi^old` into source.
  - **grad** (Green-Gauss) `Sum_f phi_f Sf` — the volume-integrated cell gradient,
    used for the explicit pressure gradient and for the Rhie-Chow flux.

  ## Rhie-Chow (collocated checkerboard fix)
  With `U` and `p` colocated at cell centres, a naive face flux built from cell
  gradients decouples odd/even pressures (checkerboard). The cure, implemented in
  `nagare.solver`, is to build the face flux from the *interpolated* momentum
  `HbyA` and correct it with the **compact** pressure Laplacian face flux
  (`face-flux-correction` below) rather than an interpolated cell gradient — that
  is precisely the Rhie-Chow interpolation."
  (:require [nagare.field :as field]))

;; ---------------------------------------------------------------------------
;; Green-Gauss gradient (volume-integrated:  g_P = Sum_f phi_f Sf)
;; ---------------------------------------------------------------------------

(defn grad-sf
  "Green-Gauss gradient of scalar `field`, returned **volume-integrated** as two
  `double[]` `[gx gy]` with `g_P = Sum_f phi_f Sf`. Divide by `V_P` for the cell
  gradient. Internal faces use linear interpolation; boundary faces use the bc
  face value (zeroGradient -> owner value, fixedValue -> prescribed)."
  [m field]
  (let [n   (int (:n-cells m))
        vals (:values field)
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles sfx (:if-sfx m) ^doubles sfy (:if-sfy m)
        ^doubles fx (:if-fx m)
        nif (int (:n-internal m))
        gx (double-array n) gy (double-array n)]
    (dotimes [f nif]
      (let [o (aget own f) p (aget nei f)
            w (aget fx f)
            pf (+ (* w (double (nth vals o))) (* (- 1.0 w) (double (nth vals p))))
            sx (aget sfx f) sy (aget sfy f)]
        (aset gx o (+ (aget gx o) (* pf sx)))
        (aset gy o (+ (aget gy o) (* pf sy)))
        (aset gx p (- (aget gx p) (* pf sx)))
        (aset gy p (- (aget gy p) (* pf sy)))))
    (doseq [pt (:patches m)]
      (let [bc (field/patch-bc field (:name pt))
            ^ints po (:owner pt)
            ^doubles psfx (:sfx pt) ^doubles psfy (:sfy pt)
            np (int (:n pt))]
        (dotimes [k np]
          (let [o (aget po k)
                pf (double (field/boundary-value bc (nth vals o)))]
            (aset gx o (+ (aget gx o) (* pf (aget psfx k))))
            (aset gy o (+ (aget gy o) (* pf (aget psfy k))))))))
    [gx gy]))

;; ---------------------------------------------------------------------------
;; Laplacian  (scalar diffusion, positive-definite / negative-Laplacian)
;; ---------------------------------------------------------------------------

(defn- gamma-face
  "Face diffusivity: `gamma` may be a constant `double` or a per-cell `double[]`
  (e.g. rAU), interpolated to the face with weight `w`."
  [gamma o p w]
  (if (number? gamma)
    (double gamma)
    (let [^doubles g gamma]
      (+ (* w (aget g o)) (* (- 1.0 w) (aget g p))))))

(defn laplacian
  "Assemble `L phi` for `-nabla.(gamma nabla phi)` (positive-definite). `gamma` is a
  constant or per-cell `double[]`. Dirichlet boundary values are folded into
  `:source`; zeroGradient boundaries add nothing. Symmetric (`upper == lower`).

  Returns `{:n :diag :upper :lower :owner :neighbour :source}`."
  [m gamma field]
  (let [n (int (:n-cells m))
        nif (int (:n-internal m))
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles area (:if-area m) ^doubles dmag (:if-dmag m)
        ^doubles fx (:if-fx m)
        diag (double-array n)
        upper (double-array nif)
        lower (double-array nif)
        src   (double-array n)]
    (dotimes [f nif]
      (let [o (aget own f) p (aget nei f)
            w (* (gamma-face gamma o p (aget fx f)) (/ (aget area f) (aget dmag f)))]
        (aset diag o (+ (aget diag o) w))
        (aset diag p (+ (aget diag p) w))
        (aset upper f (- (aget upper f) w))
        (aset lower f (- (aget lower f) w))))
    (doseq [pt (:patches m)]
      (let [bc (field/patch-bc field (:name pt))
            ^ints po (:owner pt)
            ^doubles parea (:area pt) ^doubles pdb (:db pt)
            np (int (:n pt))]
        (when (field/dirichlet? bc)
          (let [phib (double (field/bc-value bc))]
            (dotimes [k np]
              (let [o (aget po k)
                    g (gamma-face gamma o o 1.0)       ; owner-side gamma
                    w (* g (/ (aget parea k) (aget pdb k)))]
                (aset diag o (+ (aget diag o) w))
                (aset src o (+ (aget src o) (* w phib)))))))))
    {:n n :diag diag :upper upper :lower lower
     :owner own :neighbour nei :source src}))

;; ---------------------------------------------------------------------------
;; Momentum operator (ddt + upwind div(phi,U) - laplacian(nu,U)), vector source
;; ---------------------------------------------------------------------------

(defn momentum
  "Assemble the implicit momentum matrix `M` for one PISO time step:

      ddt(U) + div(phi, U) - laplacian(nu, U)

  The diag/upper/lower are component-independent (shared by u and v); the source
  is per component (`:sx :sy`) because the transient term and Dirichlet walls
  differ by component. `u-old` is the previous-step velocity vector field.

  `phi` is the face-flux field `{:internal double[] :patches {name double[]}}`.
  Returns `{:n :diag :upper :lower :owner :neighbour :sx :sy}`."
  [m {:keys [nu dt]} U phi u-old]
  (let [n (int (:n-cells m))
        nif (int (:n-internal m))
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles area (:if-area m) ^doubles dmag (:if-dmag m)
        ^doubles vol (:volumes m)
        vals (:values U)
        ^doubles phi-int (:internal phi)
        diag (double-array n)
        upper (double-array nif)
        lower (double-array nif)
        sx (double-array n) sy (double-array n)]
    ;; transient (backward Euler)
    (dotimes [c n]
      (let [r (/ (aget vol c) (double dt))
            uo (nth (:values u-old) c)]
        (aset diag c (+ (aget diag c) r))
        (aset sx c (+ (aget sx c) (* r (double (nth uo 0)))))
        (aset sy c (+ (aget sy c) (* r (double (nth uo 1)))))))
    ;; internal faces: diffusion + upwind convection
    (dotimes [f nif]
      (let [o (aget own f) p (aget nei f)
            w (* (double nu) (/ (aget area f) (aget dmag f)))
            F (aget phi-int f)]
        (aset diag o (+ (aget diag o) w))
        (aset diag p (+ (aget diag p) w))
        (aset upper f (- (aget upper f) w))
        (aset lower f (- (aget lower f) w))
        (if (>= F 0.0)
          (do (aset diag o (+ (aget diag o) F))
              (aset lower f (- (aget lower f) F)))
          (do (aset upper f (+ (aget upper f) F))
              (aset diag p (- (aget diag p) F))))))
    ;; boundary faces
    (doseq [pt (:patches m)]
      (let [bc (field/patch-bc U (:name pt))
            ^ints po (:owner pt)
            ^doubles parea (:area pt) ^doubles pdb (:db pt)
            ^doubles pphi (get (:patches phi) (:name pt))
            np (int (:n pt))
            dir (field/dirichlet? bc)
            vb (when dir (field/bc-value bc))
            vbx (double (if vb (nth vb 0) 0.0))
            vby (double (if vb (nth vb 1) 0.0))]
        (dotimes [k np]
          (let [o (aget po k)
                F (if pphi (aget pphi k) 0.0)]
            (when dir
              (let [w (* (double nu) (/ (aget parea k) (aget pdb k)))]
                (aset diag o (+ (aget diag o) w))
                (aset sx o (+ (aget sx o) (* w vbx)))
                (aset sy o (+ (aget sy o) (* w vby)))))
            ;; convection through boundary
            (if (>= F 0.0)
              (aset diag o (+ (aget diag o) F))          ; outflow: phi_f = phi_P
              (when dir                                  ; inflow with known value
                (aset sx o (- (aget sx o) (* F vbx)))
                (aset sy o (- (aget sy o) (* F vby)))))))))
    {:n n :diag diag :upper upper :lower lower
     :owner own :neighbour nei :sx sx :sy sy}))

;; ---------------------------------------------------------------------------
;; Pressure-Poisson assembly  laplacian(rAU, p) == div(phiHbyA)
;; ---------------------------------------------------------------------------

(defn pressure-eqn
  "Assemble the PISO pressure equation `nabla.(rAU nabla p) = nabla.phiHbyA` in the
  positive-definite (negated) convention `L p = b`, with `b = -div(phiHbyA)`.

  `rAU` is the per-cell reciprocal momentum diagonal (`double[]`). `phiHbyA` is the
  predicted face flux field. The pure-Neumann system is made non-singular by
  pinning reference cell `ref-cell` (large diagonal -> p_ref ~ 0).

  Returns `{:n :diag :upper :lower :owner :neighbour :source}` (SPD)."
  [m ^doubles rAU phiHbyA p-field ref-cell]
  (let [n (int (:n-cells m))
        nif (int (:n-internal m))
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles area (:if-area m) ^doubles dmag (:if-dmag m)
        ^doubles fx (:if-fx m)
        ^doubles ph-int (:internal phiHbyA)
        diag (double-array n)
        upper (double-array nif)
        lower (double-array nif)
        b (double-array n)]
    (dotimes [f nif]
      (let [o (aget own f) p (aget nei f)
            w (aget fx f)
            g (+ (* w (aget rAU o)) (* (- 1.0 w) (aget rAU p)))
            coef (* g (/ (aget area f) (aget dmag f)))
            ph (aget ph-int f)]
        (aset diag o (+ (aget diag o) coef))
        (aset diag p (+ (aget diag p) coef))
        (aset upper f (- (aget upper f) coef))
        (aset lower f (- (aget lower f) coef))
        ;; b = -div(phiHbyA): owner divergence += +ph, neighbour += -ph
        (aset b o (- (aget b o) ph))
        (aset b p (+ (aget b p) ph))))
    (doseq [pt (:patches m)]
      (let [^ints po (:owner pt)
            ^doubles pph (get (:patches phiHbyA) (:name pt))
            np (int (:n pt))]
        ;; p is zeroGradient/fixedFluxPressure -> no laplacian contribution;
        ;; boundary flux contributes to divergence (0 for impermeable walls).
        (when pph
          (dotimes [k np]
            (let [o (aget po k)] (aset b o (- (aget b o) (aget pph k))))))))
    ;; pin reference cell to remove the constant null space
    (aset diag (int ref-cell) (+ (aget diag (int ref-cell)) 1.0e15))
    {:n n :diag diag :upper upper :lower lower
     :owner own :neighbour nei :source b}))

(defn face-flux-correction
  "The compact pressure-Laplacian face flux `rAU_f |Sf|/|d| (p_N - p_P)` per
  internal face — `pEqn.flux()`. Subtract from `phiHbyA` to get the conservative,
  Rhie-Chow-damped face flux `phi`."
  [m ^doubles rAU p-field]
  (let [nif (int (:n-internal m))
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles area (:if-area m) ^doubles dmag (:if-dmag m)
        ^doubles fx (:if-fx m)
        vals (:values p-field)
        out (double-array nif)]
    (dotimes [f nif]
      (let [o (aget own f) p (aget nei f)
            w (aget fx f)
            g (+ (* w (aget rAU o)) (* (- 1.0 w) (aget rAU p)))]
        (aset out f (* g (/ (aget area f) (aget dmag f))
                       (- (double (nth vals p)) (double (nth vals o)))))))
    out))

(defn continuity-defect
  "Net face flux ∮ phi·dS out of each cell from a face-flux field `phi`
  {:internal :patches}. For an internal face the flux leaves the owner (+) and
  enters the neighbour (−); boundary patch fluxes add to their owner cell. At a
  *converged* incompressible solution this is ≈0 for every cell — the discrete
  statement of `∇·U = 0`, so it is the sharpest correctness check on the PISO/
  SIMPLE pressure correction. Returns a `double[]` indexed by cell."
  [m phi]
  (let [n (int (:n-cells m))
        out (double-array n)
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles ifl (:internal phi)]
    (dotimes [f (int (:n-internal m))]
      (let [o (aget own f) p (aget nei f) v (aget ifl f)]
        (aset out o (+ (aget out o) v))
        (aset out p (- (aget out p) v))))
    (doseq [pt (:patches m)]
      (let [^ints po (:owner pt)
            ^doubles pfl (get (:patches phi) (:name pt))]
        (when pfl
          (dotimes [k (int (:n pt))]
            (let [o (aget po k)]
              (aset out o (+ (aget out o) (aget pfl k))))))))
    out))

(defn convection-diffusion
  "Assemble the steady scalar transport system for `div(phi,φ) − laplacian(Γ,φ)`
  with first-order **upwind** convection and diffusivity `Γ` (constant or per-cell
  `double[]`). `phi` is a given (divergence-free) face-flux field. Dirichlet
  (`fixedValue`) patches fold into `:source`; `zeroGradient` adds nothing to
  diffusion and a pure outflow `phi_f = phi_P` to convection. Asymmetric in
  general (convection), so solve with BiCGStab.

  Upwind is monotone — its system is a diagonally dominant M-matrix — so the
  solution obeys a discrete maximum principle (no over/undershoot of the boundary
  values). Returns {:n :diag :upper :lower :owner :neighbour :source}."
  [m gamma phi field]
  (let [n (int (:n-cells m))
        nif (int (:n-internal m))
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles area (:if-area m) ^doubles dmag (:if-dmag m)
        ^doubles fx (:if-fx m)
        ^doubles phi-int (:internal phi)
        diag (double-array n)
        upper (double-array nif)
        lower (double-array nif)
        src (double-array n)]
    (dotimes [f nif]
      (let [o (aget own f) p (aget nei f)
            w (* (gamma-face gamma o p (aget fx f)) (/ (aget area f) (aget dmag f)))
            F (aget phi-int f)]
        (aset diag o (+ (aget diag o) w))           ; diffusion
        (aset diag p (+ (aget diag p) w))
        (aset upper f (- (aget upper f) w))
        (aset lower f (- (aget lower f) w))
        (if (>= F 0.0)                               ; upwind convection
          (do (aset diag o (+ (aget diag o) F))
              (aset lower f (- (aget lower f) F)))
          (do (aset upper f (+ (aget upper f) F))
              (aset diag p (- (aget diag p) F))))))
    (doseq [pt (:patches m)]
      (let [bc (field/patch-bc field (:name pt))
            ^ints po (:owner pt)
            ^doubles parea (:area pt) ^doubles pdb (:db pt)
            ^doubles pphi (get (:patches phi) (:name pt))
            np (int (:n pt))
            dir (field/dirichlet? bc)
            phib (when dir (double (field/bc-value bc)))]
        (dotimes [k np]
          (let [o (aget po k)
                F (if pphi (aget pphi k) 0.0)]
            (when dir
              (let [w (* (gamma-face gamma o o 1.0) (/ (aget parea k) (aget pdb k)))]
                (aset diag o (+ (aget diag o) w))
                (aset src o (+ (aget src o) (* w phib)))))
            (if (>= F 0.0)
              (aset diag o (+ (aget diag o) F))       ; outflow: phi_f = phi_P
              (when dir                               ; inflow with a known value
                (aset src o (- (aget src o) (* F phib)))))))))
    {:n n :diag diag :upper upper :lower lower
     :owner own :neighbour nei :source src}))
