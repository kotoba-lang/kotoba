(ns kotoba.tatekata.thermal
  "thermal — transient heat-conduction PDE solver (2-D explicit FDM).

  Ported 1:1 from `kami-genesis::thermal` (kami-engine, Rust, retired per
  ADR-2607010000-kotoba-runtime-sdk-cljc-migration).

  Real continuum heat transfer `dT/dt = alpha*grad^2(T) + Q/(rho*c)` on a
  uniform grid, with a travelling volumetric heat source (Gaussian /
  Goldak-style) for robotic arc welding, and Dirichlet / Neumann boundary
  conditions. This is what `kotoba.tatekata.weld-field`'s weld-pass fusion
  tracking is built on: the fusion zone, heat-affected zone and cool-down are
  emergent from conduction, not scripted.

  Honest scope: 2-D explicit (forward-Euler) FDM — first-order, CFL-bounded,
  single material, no phase-change latent heat or thermo-mechanical coupling
  (those need an implicit / FEM thermo-mechanical solver). It is, however, a
  genuine PDE: verified against the 1-D steady-state analytic profile and an
  energy-conservation invariant.

  A field is a map:
  `{:thermal/nx :thermal/ny :thermal/h :thermal/alpha :thermal/ambient
    :thermal/t-melt :thermal/rho-c :thermal/h-conv :thermal/t :thermal/peak
    :thermal/bc}` — `:thermal/t` (temperature) and `:thermal/peak` (peak
  temperature ever reached, i.e. fusion evidence) are flat vectors, row-major
  (`j * nx + i`). `:thermal/bc` is `[-x +x -y +y]`, each entry either
  `:neumann` (insulated / zero normal gradient) or `[:dirichlet <celsius>]`
  (fixed temperature) — see `dirichlet`/`neumann` below. Functions here are
  pure: `step`/`step-multi` return an updated field. No network, no I/O.")

(defn- exp* [x] #?(:clj (Math/exp x) :cljs (js/Math.exp x)))
(def ^:private pi #?(:clj Math/PI :cljs js/Math.PI))

(defn dirichlet
  "A fixed-temperature (°C) boundary condition."
  [v] [:dirichlet v])

(def neumann
  "An insulated (zero normal gradient) boundary condition."
  :neumann)

(defn- idx [nx i j] (+ (* j nx) i))

(defn make-field
  "`nx`/`ny` are clamped to a minimum of 3. `h` = cell size (m), `alpha` =
  thermal diffusivity (m^2/s), `ambient` = ambient temperature (°C), `t-melt`
  = fusion threshold (°C). Defaults: `:thermal/rho-c` 4.0e6 (~steel,
  rho*c ~= 7850*500), `:thermal/h-conv` 0.0 (insulated / pure conduction),
  `:thermal/bc` all `neumann`."
  [nx ny h alpha ambient t-melt]
  (let [nx (max 3 nx)
        ny (max 3 ny)
        n (* nx ny)]
    {:thermal/nx nx
     :thermal/ny ny
     :thermal/h h
     :thermal/alpha alpha
     :thermal/ambient ambient
     :thermal/t-melt t-melt
     :thermal/rho-c 4.0e6
     :thermal/h-conv 0.0
     :thermal/t (vec (repeat n (double ambient)))
     :thermal/peak (vec (repeat n (double ambient)))
     :thermal/bc [neumann neumann neumann neumann]}))

(defn with-bc
  "`bc` = `[-x +x -y +y]` boundary conditions (see `dirichlet`/`neumann`)."
  [field bc]
  (assoc field :thermal/bc bc))

(defn with-rho-c
  "Override the lumped volumetric heat capacity rho*c (J/m^3K). Lower = a
  given power raises temperature faster (use to calibrate the weld source)."
  [field rho-c]
  (assoc field :thermal/rho-c rho-c))

(defn with-convection
  "Enable Newton convective heat loss to ambient at volumetric rate `k`
  (1/s): each cell sheds `k*(T - ambient)` per second, modelling a member
  cooling to surrounding air after the arc passes. Default 0 = insulated
  (pure conduction, heat conserved). Sub-step (via `cfl-dt`) so `k*dt < 1`
  for stability."
  [field k]
  (assoc field :thermal/h-conv (max k 0.0)))

(defn cell-center
  [{:keys [:thermal/h]} i j]
  [(* (+ i 0.5) h) (* (+ j 0.5) h)])

(defn temp
  [{:keys [:thermal/nx :thermal/t]} i j]
  (nth t (idx nx i j)))

(defn cfl-dt
  "The largest stable explicit timestep (2-D CFL: alpha*dt/h^2 <= 1/4)."
  [{:keys [:thermal/h :thermal/alpha]}]
  (/ (* 0.2 h h) (max alpha 1e-9)))

(defn- bc-val [bc interior]
  (if (and (vector? bc) (= (first bc) :dirichlet))
    (second bc)
    interior))

(defn- dirichlet-v [bc]
  (when (and (vector? bc) (= (first bc) :dirichlet))
    (second bc)))

(defn- apply-dirichlet
  "Re-apply Dirichlet edges exactly (after an explicit conduction step)."
  [{:keys [:thermal/nx :thermal/ny :thermal/bc :thermal/t] :as field}]
  (let [[bx0 bx1 by0 by1] bc
        t (as-> t t
            (if-let [v (dirichlet-v bx0)]
              (reduce (fn [t j] (assoc t (idx nx 0 j) v)) t (range ny))
              t)
            (if-let [v (dirichlet-v bx1)]
              (reduce (fn [t j] (assoc t (idx nx (dec nx) j) v)) t (range ny))
              t)
            (if-let [v (dirichlet-v by0)]
              (reduce (fn [t i] (assoc t (idx nx i 0) v)) t (range nx))
              t)
            (if-let [v (dirichlet-v by1)]
              (reduce (fn [t i] (assoc t (idx nx i (dec ny)) v)) t (range nx))
              t))]
    (assoc field :thermal/t t)))

(defn step-multi
  "Advance by `dt` with *several* simultaneous heat sources, each a
  `[sx sy power sigma]` tuple (world position, total power in W, Gaussian
  radius in m) whose contributions superpose. Models multi-pass / multi-torch
  welding. An empty `sources` seq = pure conduction."
  [{:keys [:thermal/nx :thermal/ny :thermal/h :thermal/alpha :thermal/ambient
           :thermal/rho-c :thermal/h-conv :thermal/t :thermal/peak :thermal/bc]
    :as field}
   sources dt]
  (let [inv-h2 (/ 1.0 (* h h))
        [bx0 bx1 by0 by1] bc
        n (* nx ny)
        prev t
        [tt pk]
        (reduce
         (fn [[tt pk] kk]
           (let [i (mod kk nx)
                 j (quot kk nx)
                 c (nth prev kk)
                 l (if (pos? i) (nth prev (idx nx (dec i) j)) (bc-val bx0 c))
                 r (if (< (inc i) nx) (nth prev (idx nx (inc i) j)) (bc-val bx1 c))
                 d (if (pos? j) (nth prev (idx nx i (dec j))) (bc-val by0 c))
                 u (if (< (inc j) ny) (nth prev (idx nx i (inc j))) (bc-val by1 c))
                 lap (* (- (+ l r d u) (* 4.0 c)) inv-h2)
                 [cx cy] (cell-center field i j)
                 q (reduce
                    (fn [q [sx sy power sigma]]
                      (let [two-sig2 (* 2.0 sigma sigma)
                            norm (/ power (* pi two-sig2 rho-c))
                            ddx (- cx sx)
                            ddy (- cy sy)
                            dist2 (+ (* ddx ddx) (* ddy ddy))]
                        (+ q (* norm (exp* (/ (- dist2) two-sig2))))))
                    0.0
                    sources)
                 conv (* h-conv (- c ambient))
                 next0 (+ c (* (+ (* alpha lap) q (- conv)) dt))
                 nxt (max next0 ambient)
                 prev-peak (nth peak kk)
                 nxt-peak (if (> nxt prev-peak) nxt prev-peak)]
             [(assoc! tt kk nxt) (assoc! pk kk nxt-peak)]))
         [(transient t) (transient peak)]
         (range n))]
    (apply-dirichlet (assoc field :thermal/t (persistent! tt) :thermal/peak (persistent! pk)))))

(defn step
  "Advance by `dt` with a single travelling volumetric heat source: total
  power `power` (W) deposited as a Gaussian of radius `sigma` (m) centred at
  the world position `(sx, sy)` (m)."
  [field sx sy power sigma dt]
  (step-multi field [[sx sy power sigma]] dt))

(defn max-temp [{:keys [:thermal/ambient :thermal/t]}]
  (reduce max ambient t))

(defn fused-fraction
  "Fraction of cells whose peak temperature reached fusion."
  [{:keys [:thermal/t-melt :thermal/peak]}]
  (/ (double (count (filter #(>= % t-melt) peak))) (double (count peak))))

(defn total-heat
  "Total thermal energy above ambient (proportional to sum(T-ambient)), for
  conservation checks."
  [{:keys [:thermal/ambient :thermal/t]}]
  (reduce + (map #(- % ambient) t)))
