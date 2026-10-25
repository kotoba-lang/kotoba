(ns kami-cfd.duct
  "**Internal** (duct / enclosure / cold-plate) flow on the same D3Q19
  lattice-Boltzmann kernel as `kami-cfd.d3`, but with internal-flow boundary
  conditions instead of the vehicle far-field ones.

  Why this namespace exists. `kami-cfd.d3` solves *external* aerodynamics: a
  body sits in a freestream, the domain sides are free-slip far field, the
  ground is no-slip, and the x-ends are inflow/outflow. That boundary set is
  exactly wrong for a sealed box with a fan: there is no far field, every
  wall is no-slip, and air enters and leaves only through designated patches.
  Reusing `d3/run` on an enclosure would silently model a box floating in a
  wind tunnel with leaky walls.

  What is shared and what is not:
  - **Shared** (from `kami-cfd.d3`): the D3Q19 lattice (`ex`/`ey`/`ez`/`w`/
    `opp`), `feq`, and `collide!` — the BGK + Smagorinsky LES collision.
    Collision is per-cell and reads no neighbour, so it is boundary-agnostic
    by construction and safe to share. One lattice, one source of truth.
  - **Not shared**: streaming and boundaries. This namespace supplies its own
    `stream!` where *all six domain faces are no-slip walls* except the
    patches declared as inlet/outlet.

  Boundary conditions implemented:
  - **Solid cells / walls** — halfway bounce-back (`opp`), the same treatment
    `d3` uses for the body. Second-order accurate for a wall halfway between
    nodes, which is what the Poiseuille validation below relies on.
  - **Velocity inlet** — equilibrium at a prescribed velocity (a fan face).
  - **Outlet** — zero-gradient copy from the neighbour cell one step inside
    (an open vent). Mass is not forced to balance; the outlet lets the solver
    find its own flux.
  - **Periodic axes** — `:periodic #{:x :y :z}`. An out-of-domain upstream on
    a periodic axis wraps to the far side instead of bouncing back. Needed for
    any streamwise-invariant case (the Poiseuille verification below) and for
    repeating geometry. Without it every face is a wall, and a body force in a
    sealed box only pressurises it — which is exactly what the first version
    of this namespace did, and what the verification case caught.
  - **Body force** — optional uniform acceleration, used by the validation
    case (force-driven Poiseuille) and available for buoyancy studies.

  **Validation is not optional here and is not a smoke test.** `poiseuille`
  runs force-driven plane Poiseuille flow, whose steady solution is exactly
  u(y) = (G/(2 nu)) * y * (H - y). `validate-poiseuille` returns the relative
  L2 error against that closed form. This is the canonical LBM verification
  case: if the L2 error is not small, the bounce-back walls or the viscosity
  mapping are wrong and every enclosure number this namespace produces is
  meaningless. Run it before trusting anything else.

  **Regime limit — see `reachable-reynolds` below before using this on an
  enclosure.** This is a laminar-to-moderate-Re tool; a fan-cooled computer
  case is Re ~2e4 and out of reach on any grid affordable single-threaded.

  **What this namespace does NOT compute.** Flow only — velocity, volumetric
  flux, stagnant-region fraction. It carries no energy equation, so it cannot
  give component temperatures. The one temperature it does give,
  `bulk-delta-t`, is not a CFD result at all: it is steady-state energy
  conservation on the through-flow (dT = W / (rho*cp*Q)), i.e. how much the
  air heats up on its way through. Junction temperatures need a conjugate
  heat-transfer solver, which this is not.

  Zero-dep portable `.cljc` — runs on JVM Clojure, ClojureScript and nbb."
  (:require [kami-cfd.d3 :as d3]))

;; ---------------------------------------------------------------------------
;; Domain construction
;; ---------------------------------------------------------------------------

(defn domain
  "A lattice domain `nx`x`ny`x`nz` whose solid cells are decided by
  `solid-fn` — a predicate `(fn [x y z] boolean)`. Cell indexing matches
  `kami-cfd.d3`: n = (z*ny + y)*nx + x."
  [nx ny nz solid-fn]
  (let [n-cells (* nx ny nz)
        solid (d3/bool-array n-cells)]
    (dotimes [z nz]
      (dotimes [y ny]
        (dotimes [x nx]
          (when (solid-fn x y z)
            (aset solid (+ (* (+ (* z ny) y) nx) x) true)))))
    {:nx nx :ny ny :nz nz :solid solid
     :solid-count (count (filter true? (seq solid)))}))

(defn boxes->solid-fn
  "Solid predicate from axis-aligned boxes given in lattice cells:
  `[[x0 y0 z0] [x1 y1 z1]]` (half-open upper bound)."
  [boxes]
  (fn [x y z]
    (boolean
     (some (fn [[[x0 y0 z0] [x1 y1 z1]]]
             (and (>= x x0) (< x x1) (>= y y0) (< y y1) (>= z z0) (< z z1)))
           boxes))))

(defn patch
  "A boundary patch: which domain face, and which cells of that face.
  `face` is one of :x-min :x-max :y-min :y-max :z-min :z-max.
  `in?` is `(fn [a b] boolean)` over the two in-plane cell coordinates, in
  the order (y,z) for x faces, (x,z) for y faces, (x,y) for z faces.
  `kind` is :inlet or :outlet. `u` is the prescribed speed in lattice units
  (ignored for :outlet), directed **along the inward normal** — so a
  **negative `u` is a suction patch**: a fan pulling air out through this face.
  That is the correct way to model a blower-cooled enclosure: the blower is
  the mover, so prescribe velocity where the blower is and leave the intake
  vent a passive :outlet (zero-gradient, i.e. open to ambient).

  **Prescribing velocity on the passive vent instead is not equivalent** and
  will over-constrain mass: a large velocity inlet feeding a small
  zero-gradient outlet cannot conserve mass, so the domain pressurises, the
  outlet flux collapses toward zero and nearly every cell reads as stagnant.
  If inlet and outlet fluxes do not balance, suspect this first."
  [face kind in? u]
  {:face face :kind kind :in? in? :u u})

(defn full-face
  "Convenience: a patch covering an entire domain face."
  [face kind u]
  (patch face kind (fn [_ _] true) u))

;; ---------------------------------------------------------------------------
;; Solver state
;; ---------------------------------------------------------------------------

(defn- idx [nx ny x y z] (+ (* (+ (* z ny) y) nx) x))

(defn- face-normal
  "Inward unit normal of a domain face, as [dx dy dz]."
  [face]
  (case face
    :x-min [1 0 0] :x-max [-1 0 0]
    :y-min [0 1 0] :y-max [0 -1 0]
    :z-min [0 0 1] :z-max [0 0 -1]))

(defn- face-cells
  "Seq of [x y z] lattice cells lying on `face`."
  [nx ny nz face]
  (case face
    :x-min (for [z (range nz) y (range ny)] [0 y z])
    :x-max (for [z (range nz) y (range ny)] [(dec nx) y z])
    :y-min (for [z (range nz) x (range nx)] [x 0 z])
    :y-max (for [z (range nz) x (range nx)] [x (dec ny) z])
    :z-min (for [y (range ny) x (range nx)] [x y 0])
    :z-max (for [y (range ny) x (range nx)] [x y (dec nz)])))

(defn- in-plane
  "The two in-plane coordinates of cell [x y z] on `face`, in the order
  `patch`'s `in?` expects."
  [face [x y z]]
  (case face
    (:x-min :x-max) [y z]
    (:y-min :y-max) [x z]
    (:z-min :z-max) [x y]))

(defn duct-new
  "Solver state for internal flow.
  `nu` is the kinematic viscosity in lattice units; tau = 0.5 + 3*nu.
  `patches` is a seq from `patch`/`full-face`.
  `force` is an optional uniform body acceleration `[gx gy gz]` (lattice
  units), applied every collision — used by the Poiseuille validation.
  `periodic` is a set of axis keywords (`:x`/`:y`/`:z`) to wrap instead of
  walling. `u0` is the reference speed used for normalisation and reporting."
  [dom {:keys [nu patches force u0 periodic]}]
  (let [{:keys [nx ny nz]} dom
        nu (double (or nu 0.02))
        tau (+ 0.5 (* 3.0 nu))
        u0 (double (or u0 0.05))
        n-cells (* nx ny nz)
        f (double-array (* n-cells 19))]
    (dotimes [n n-cells]
      (dotimes [i 19]
        (aset ^doubles f (+ (* n 19) i) (double (d3/feq i 1.0 0.0 0.0 0.0)))))
    ;; Resolve patches to concrete cell-index sets once, not per step.
    (let [resolved
          (mapv (fn [{:keys [face kind in? u]}]
                  (let [[dx dy dz] (face-normal face)
                        cells (->> (face-cells nx ny nz face)
                                   (filter (fn [c] (apply in? (in-plane face c))))
                                   (remove (fn [[x y z]]
                                             (aget ^booleans (:solid dom) (idx nx ny x y z))))
                                   vec)]
                    {:kind kind
                     :u (double (or u 0.0))
                     :dir [dx dy dz]
                     :cells (mapv (fn [[x y z]]
                                    [(idx nx ny x y z)
                                     (idx nx ny (+ x dx) (+ y dy) (+ z dz))])
                                  cells)}))
                (or patches []))]
      {:nx nx :ny ny :nz nz :tau tau :u0 u0 :nu nu
       :f f :ftmp (aclone f)
       :periodic (or periodic #{})
       :force (or force [0.0 0.0 0.0])
       :patches resolved
       :body {:nx nx :ny ny :nz nz :solid (:solid dom)
              ;; d3/collide! reads :solid via solid3-at?; :frontal-cells is
              ;; only used by the vehicle Cd path, never by collision.
              :frontal-cells 1}})))

;; ---------------------------------------------------------------------------
;; Boundary application
;; ---------------------------------------------------------------------------

(defn- apply-patches!
  "Velocity inlets set equilibrium at the prescribed velocity; outlets copy
  the neighbour one cell inside (zero gradient). Mutates `(:f lbm)`."
  [lbm]
  (let [f (:f lbm)]
    (doseq [{:keys [kind u dir cells]} (:patches lbm)]
      (let [[dx dy dz] dir]
        (if (= :inlet kind)
          (doseq [[n _] cells]
            (dotimes [i 19]
              (aset ^doubles f (+ (* n 19) i)
                    (double (d3/feq i 1.0 (* u dx) (* u dy) (* u dz))))))
          (doseq [[n nin] cells]
            (dotimes [i 19]
              (aset ^doubles f (+ (* n 19) i)
                    (aget ^doubles f (+ (* nin 19) i))))))))
    lbm))

(defn- body-force!
  "Uniform acceleration via a shift of the equilibrium velocity (Guo-style
  first order, adequate at the small forcing used for validation). Mutates."
  [lbm]
  (let [[gx gy gz] (:force lbm)]
    (when (or (not (zero? gx)) (not (zero? gy)) (not (zero? gz)))
      (let [{:keys [nx ny nz tau]} lbm f (:f lbm) solid (:solid (:body lbm))
            ncells (* nx ny nz)]
        (dotimes [n ncells]
          (when-not (aget ^booleans solid n)
            (dotimes [i 19]
              (let [exi (aget ^ints d3/ex i) eyi (aget ^ints d3/ey i) ezi (aget ^ints d3/ez i)
                    wi (aget ^doubles d3/w i)
                    proj (+ (* exi gx) (* eyi gy) (* ezi gz))]
                (aset ^doubles f (+ (* n 19) i)
                      (+ (aget ^doubles f (+ (* n 19) i)) (* 3.0 wi proj)))))))))
    lbm))

(defn- stream!
  "Streaming, PULL form — each cell writes only its own ftmp. Upstream that
  is solid **or outside the domain** gives halfway bounce-back: every domain
  face is a no-slip wall. Inlet/outlet patches are re-applied afterwards and
  overwrite their own cells, so declaring a patch is what opens a hole in an
  otherwise sealed box."
  [lbm]
  (let [{:keys [nx ny nz]} lbm
        per (:periodic lbm)
        px (contains? per :x) py (contains? per :y) pz (contains? per :z)
        f (:f lbm) ftmp (:ftmp lbm) solid (:solid (:body lbm))
        ncells (* nx ny nz) nxy (* nx ny)
        wrap (fn [v n] (cond (< v 0) (+ v n) (>= v n) (- v n) :else v))]
    (dotimes [n ncells]
      (let [z (quot n nxy) y (mod (quot n nx) ny) x (mod n nx)]
        (if (aget ^booleans solid n)
          (dotimes [j 19] (aset ^doubles ftmp (+ (* n 19) j) 0.0))
          (dotimes [j 19]
            (let [rx (- x (aget ^ints d3/ex j))
                  ry (- y (aget ^ints d3/ey j))
                  rz (- z (aget ^ints d3/ez j))
                  sx (if px (wrap rx nx) rx)
                  sy (if py (wrap ry ny) ry)
                  sz (if pz (wrap rz nz) rz)
                  outside (or (< sx 0) (>= sx nx) (< sy 0) (>= sy ny) (< sz 0) (>= sz nz))
                  val (if outside
                        (aget ^doubles f (+ (* n 19) (aget ^ints d3/opp j)))  ; wall: bounce-back
                        (let [sn (+ (* (+ (* sz ny) sy) nx) sx)]
                          (if (aget ^booleans solid sn)
                            (aget ^doubles f (+ (* n 19) (aget ^ints d3/opp j)))
                            (aget ^doubles f (+ (* sn 19) j)))))]
              (aset ^doubles ftmp (+ (* n 19) j) (double val)))))))
    (apply-patches! (assoc lbm :f ftmp :ftmp f))))

(defn step [lbm] (stream! (body-force! (d3/collide! lbm))))

(defn run [lbm steps]
  (loop [s 0 l lbm] (if (>= s steps) l (recur (inc s) (step l)))))

;; ---------------------------------------------------------------------------
;; Field probes
;; ---------------------------------------------------------------------------

(defn cell-macros
  "`[rho ux uy uz]` at lattice cell [x y z]. Solid cells give all zeros."
  [lbm x y z]
  (let [{:keys [nx ny]} lbm f (:f lbm) solid (:solid (:body lbm))
        n (idx nx ny x y z)]
    (if (aget ^booleans solid n)
      [0.0 0.0 0.0 0.0]
      (loop [i 0 rho 0.0 mx 0.0 my 0.0 mz 0.0]
        (if (= i 19)
          (if (pos? rho) [rho (/ mx rho) (/ my rho) (/ mz rho)] [rho 0.0 0.0 0.0])
          (let [fi (aget ^doubles f (+ (* n 19) i))]
            (recur (inc i) (+ rho fi)
                   (+ mx (* fi (aget ^ints d3/ex i)))
                   (+ my (* fi (aget ^ints d3/ey i)))
                   (+ mz (* fi (aget ^ints d3/ez i))))))))))

(defn speed-at [lbm x y z]
  (let [[_ ux uy uz] (cell-macros lbm x y z)]
    (d3/sqrt* (+ (* ux ux) (* uy uy) (* uz uz)))))

(defn patch-flux
  "Volumetric flux (lattice units, cells^3/step) through the `kind` patches,
  as the sum of the inward-normal velocity component over patch cells. Signed:
  positive means net flow in the patch's inward direction."
  [lbm kind]
  (let [{:keys [nx ny]} lbm]
    (reduce
     + 0.0
     (for [{k :kind dir :dir cells :cells} (:patches lbm)
           :when (= k kind)
           [n _] cells]
       (let [nxy (* nx ny)
             z (quot n nxy) y (mod (quot n nx) ny) x (mod n nx)
             [_ ux uy uz] (cell-macros lbm x y z)
             [dx dy dz] dir]
         (+ (* ux dx) (* uy dy) (* uz dz)))))))

(defn stagnant-fraction
  "Fraction of fluid cells whose speed is below `frac` of u0 — the
  dead-zone measure. Reported, never silently ignored: a large stagnant
  fraction with a healthy total flux means the air is bypassing something."
  [lbm frac]
  (let [{:keys [nx ny nz u0]} lbm solid (:solid (:body lbm))
        thr (* frac u0)]
    (loop [z 0 fluid 0 dead 0]
      (if (= z nz)
        (if (pos? fluid) (/ (double dead) (double fluid)) 0.0)
        (let [[f' d']
              (loop [y 0 fl fluid dd dead]
                (if (= y ny) [fl dd]
                    (let [[fl' dd']
                          (loop [x 0 fl2 fl dd2 dd]
                            (if (= x nx) [fl2 dd2]
                                (if (aget ^booleans solid (idx nx ny x y z))
                                  (recur (inc x) fl2 dd2)
                                  (recur (inc x) (inc fl2)
                                         (if (< (speed-at lbm x y z) thr) (inc dd2) dd2)))))]
                      (recur (inc y) fl' dd'))))]
          (recur (inc z) f' d'))))))


;; ---------------------------------------------------------------------------
;; Convergence-based stopping (2026-07-27).
;;
;; `run` takes a fixed step count, which is an arbitrary number chosen by the
;; caller. A field that has NOT reached steady state looks exactly like one
;; that has — same shape, same probe functions, no complaint. That is the same
;; class of quiet-wrongness as a boolean feature that no-ops: the result is
;; returned with full confidence and nothing says it is unfinished.
;;
;; `run-until-steady` iterates until the largest per-cell velocity change
;; between successive steps falls below `tol`, and REPORTS which happened:
;; `:converged` with the step count, or `:max-steps` with theremaining residual. The
;; caller can then refuse to publish a non-converged number instead of
;; publishing it unknowingly.
;;
;; Cost note: the residual needs the velocity field twice, so a checked step is
;; more expensive than a bare one. `check-every` amortises that — the residual
;; is only evaluated every Nth step, and the reported residual is the last one
;; measured.
;; ---------------------------------------------------------------------------

(defn- velocity-snapshot
  "Flat array of (ux,uy,uz) for every cell — solid cells contribute zeros."
  [lbm]
  (let [{:keys [nx ny nz]} lbm
        n (* nx ny nz)
        out (double-array (* n 3))]
    (dotimes [i n]
      (let [nxy (* nx ny)
            z (quot i nxy) y (mod (quot i nx) ny) x (mod i nx)
            [_ ux uy uz] (cell-macros lbm x y z)]
        (aset ^doubles out (* i 3) (double ux))
        (aset ^doubles out (+ (* i 3) 1) (double uy))
        (aset ^doubles out (+ (* i 3) 2) (double uz))))
    out))

(defn- max-abs-diff [^doubles a ^doubles b]
  (let [n (alength a)]
    (loop [i 0 m 0.0]
      (if (= i n) m
          (recur (inc i) (max m (Math/abs (- (aget a i) (aget b i)))))))))

(defn run-until-steady
  "Iterate until steady, or until `max-steps`. Returns
  `{:lbm :status :steps :residual :tol}` where `:status` is `:converged` or
  `:max-steps`.

  Give the criterion as **`:rel-tol`, a fraction of `u0`** — that is the only
  form that means anything physically, and it is the recommended option.
  `:tol` (absolute, lattice units) is still accepted but is easy to get badly
  wrong: with u0 = 0.05, an innocent-looking `:tol 1e-7` is 2e-6 of the flow
  scale and will run essentially forever on any real domain. `:rel-tol` is
  scaled by u0 for you; 1e-4 is a reasonable engineering criterion, 1e-5 is
  strict. If both are given, `:rel-tol` wins.

  A `:max-steps` result is not a failure to be ignored: it means the reported
  field is still evolving and any flux read off it is provisional. The returned
  map always carries `:tol` (the absolute value actually used) and
  `:rel-tol-used` so the criterion is never implicit."
  ([lbm] (run-until-steady lbm {}))
  ([lbm {:keys [tol rel-tol max-steps check-every]}]
   (let [rel (when rel-tol (double rel-tol))
         tol (double (cond rel (* rel (:u0 lbm))
                           tol tol
                           :else (* 1.0e-4 (:u0 lbm))))
         max-steps (long (or max-steps 20000))
         check-every (long (or check-every 50))]
     (loop [s 0 l lbm prev (velocity-snapshot lbm) resid ##Inf]
       (if (>= s max-steps)
         {:lbm l :status :max-steps :steps s :residual resid :tol tol
          :rel-tol-used (when rel rel)}
         (let [l' (reduce (fn [acc _] (step acc)) l (range check-every))
               s' (+ s check-every)
               cur (velocity-snapshot l')
               r (max-abs-diff cur prev)]
           (if (<= r tol)
             {:lbm l' :status :converged :steps s' :residual r :tol tol
              :rel-tol-used (when rel rel)}
             (recur s' l' cur r))))))))

;; ---------------------------------------------------------------------------
;; Validation: force-driven plane Poiseuille flow
;; ---------------------------------------------------------------------------

(defn poiseuille-analytic
  "Exact steady plane-Poiseuille profile between no-slip walls a distance
  `h` apart, driven by uniform acceleration `g` at viscosity `nu`:
  u(y) = (g / (2 nu)) * y * (h - y)."
  [g nu h y]
  (* (/ g (* 2.0 nu)) y (- h y)))

(defn poiseuille
  "Force-driven plane Poiseuille flow: no-slip walls in y (halfway
  bounce-back at y = -1/2 and y = ny - 1/2), **periodic in x and z**, driven
  by uniform acceleration `g` in +x at viscosity `nu`.

  Periodicity in the streamwise direction is not optional. The first version
  of this function left every face a wall and the flow never developed — a
  sealed box under a body force just pressurises. The verification below is
  what surfaced that, which is the entire reason it exists."
  [ny g nu]
  (let [nx 3 nz 3
        dom (domain nx ny nz (fn [_ _ _] false))]
    (duct-new dom {:nu nu :force [g 0.0 0.0] :u0 1.0
                   :patches [] :periodic #{:x :z}})))

(defn validate-poiseuille
  "Run force-driven Poiseuille and compare the centre-column y profile to
  `poiseuille-analytic`. Returns
  `{:l2-rel :u-max-sim :u-max-exact :profile-sim :profile-exact :ny :steps
    :tol :pass?}`. `pass?` is the gate: relative L2 error <= `tol`
  (default 0.02).

  **Where the walls actually are.** With halfway bounce-back the wall sits half
  a cell *outside* the first fluid node, so for `ny` fluid nodes the walls are
  at y = -1/2 and y = ny - 1/2: the channel height is **H = ny** and fluid node
  j (0-based) is at **y = j + 1/2**. Getting this convention wrong produces a
  clean systematic error rather than noise — the first version of this function
  used H = ny+1 and y = j+1, which under-predicted the analytic peak by ~17%
  and read as a 22% L2 'solver error' when the solver was in fact right to
  ~1%. The reference implementation is part of what a verification case has to
  get right."
  ([] (validate-poiseuille 21 1.0e-6 0.05 4000 0.02))
  ([ny g nu steps tol]
   (let [lbm (run (poiseuille ny g nu) steps)
         h (double ny)
         xs (long (/ 3 2)) zs (long (/ 3 2))
         sim (mapv (fn [j] (let [[_ ux _ _] (cell-macros lbm xs j zs)] ux)) (range ny))
         exact (mapv (fn [j] (poiseuille-analytic g nu h (+ 0.5 (double j)))) (range ny))
         num (reduce + 0.0 (map (fn [a b] (let [d (- a b)] (* d d))) sim exact))
         den (reduce + 0.0 (map (fn [b] (* b b)) exact))
         l2 (if (pos? den) (d3/sqrt* (/ num den)) ##Inf)]
     {:l2-rel l2
      :u-max-sim (apply max sim)
      :u-max-exact (apply max exact)
      :profile-sim sim
      :profile-exact exact
      :ny ny :steps steps :tol tol
      :pass? (<= l2 tol)})))


;; ---------------------------------------------------------------------------
;; Reynolds-number reachability — read this before using it on an enclosure.
;;
;; This solver is a **laminar-to-moderate-Re internal flow** tool. On a grid
;; you can afford single-threaded, it cannot reach the Reynolds number of a
;; fan-cooled computer enclosure, and the arithmetic is not close:
;;
;;   MK-1 enclosure, 6 mm cells (measured 2026-07-27):
;;     lattice   Re = u0*L/nu = 0.05*31/0.02       =     78
;;     physical  Re = 3 m/s * 0.093 m / 1.5e-5     = 18,400
;;   To match at u0=0.05 on 31 cells you would need nu = 8.4e-5, i.e.
;;   tau = 0.50025 — LBM loses stability as tau -> 0.5 — and the diffusive
;;   settling time L^2/nu = 1.1e7 steps, about 26 days at this throughput.
;;
;; So do not point this at an enclosure and read the flux as an answer. Two
;; honest uses remain: (1) verification and method development, where the
;; Poiseuille case gives a closed-form check; (2) genuinely low-Re internal
;; flow (fine channels, cold plates, creeping flow).
;;
;; For turbulent enclosure/vehicle airflow, route to a solver built for it —
;; `kotoba-lang/kami-engine-cae-solver` already carries OpenFOAM evidence
;; runners. Choosing the wrong solver and reporting its number confidently is
;; a worse failure than not having a number.
;;
;; `reachable-reynolds` below makes the envelope computable instead of
;; folklore, so a caller can check before spending an hour.
;; ---------------------------------------------------------------------------

(defn reynolds
  "Lattice Reynolds number u0*L/nu for a characteristic length `l-cells`."
  [lbm l-cells]
  (/ (* (:u0 lbm) (double l-cells)) (:nu lbm)))

(defn reachable-reynolds
  "Given a characteristic length in cells, report the Re envelope this
  substrate can actually deliver, and what a target Re would cost.

  Returns `{:re-current :re-max-stable :nu-for-target :tau-for-target
  :settling-steps-for-target :feasible?}`. `:feasible?` is false when the
  target needs tau within `tau-margin` of 0.5 (unstable) or more than
  `step-budget` settling steps — i.e. when the honest answer is to use a
  different solver."
  ([lbm l-cells target-re] (reachable-reynolds lbm l-cells target-re 0.01 1000000))
  ([lbm l-cells target-re tau-margin step-budget]
   (let [l (double l-cells)
         nu-min (/ tau-margin 3.0)                 ; tau = 0.5 + 3nu
         re-max (/ (* 0.1 l) nu-min)               ; u0 <= ~0.1 for stability
         nu-t (/ (* (:u0 lbm) l) (double target-re))
         tau-t (+ 0.5 (* 3.0 nu-t))
         settle (/ (* l l) nu-t)]
     {:re-current (reynolds lbm l-cells)
      :re-max-stable re-max
      :nu-for-target nu-t
      :tau-for-target tau-t
      :settling-steps-for-target settle
      :feasible? (and (> tau-t (+ 0.5 tau-margin)) (<= settle step-budget))})))

;; ---------------------------------------------------------------------------
;; Engineering conversions — lattice units are not millimetres
;; ---------------------------------------------------------------------------

(defn lattice->cfm
  "Convert a lattice patch flux to CFM given the cell size and the physical
  inlet speed the lattice u0 represents.

  Lattice results are dimensionless. The bridge is one length scale
  (`cell-mm`) and one velocity scale: the lattice inlet speed `u-lat` stands
  for the physical inlet speed `u-ms`. Volumetric flow is
  Q = flux_lattice * cell_area * (u_ms / u_lat), then m3/s -> CFM.

  **This conversion is where a plausible-looking CFD number can quietly
  become wrong**, so the scale factors are arguments, never hidden defaults."
  [flux-lattice cell-mm u-lat u-ms]
  (let [cell-m (/ cell-mm 1000.0)
        area (* cell-m cell-m)
        q-m3s (* flux-lattice area (/ u-ms u-lat))]
    {:q-m3s q-m3s :cfm (* q-m3s 2118.88)}))

(defn bulk-delta-t
  "Steady-state bulk air temperature rise across the enclosure, K:
  dT = W / (rho * cp * Q). **Not a CFD result** — plain energy conservation
  on the through-flow, using CFD only for Q. It bounds how hot the *exhaust
  air* gets; it says nothing about component junction temperatures, which
  need conjugate heat transfer this namespace does not implement."
  [watts q-m3s]
  (let [rho 1.164 cp 1005.0]        ; air at ~30 C, 1 atm
    (if (pos? q-m3s) (/ watts (* rho cp q-m3s)) ##Inf)))
