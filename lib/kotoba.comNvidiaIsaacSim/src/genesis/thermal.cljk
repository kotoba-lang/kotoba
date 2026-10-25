(ns genesis.thermal
  "Transient heat-conduction PDE solver (2-D explicit FDM).

  Real continuum heat transfer dT/dt = alpha*grad^2(T) + Q/(rho*c) on a
  uniform grid, with a travelling volumetric heat source
  (Gaussian/Goldak-style) and Dirichlet/Neumann boundary conditions.

  Honest scope: 2-D explicit (forward-Euler) FDM — first-order,
  CFL-bounded, single material, no phase-change latent heat or
  thermo-mechanical coupling. Verified against the 1-D steady-state
  analytic profile and an energy-conservation invariant. Clean-room
  (no NVIDIA).

  A `ThermalField` is a plain map:
    {:nx :ny :h :alpha :ambient :t-melt :rho-c :h-conv :t :peak :bc}
  where `:t`/`:peak` are vectors of length nx*ny (row-major, j*nx+i) and
  `:bc` is a 4-vector of boundary conditions [-x +x -y +y], each either
  `[:dirichlet v]` or `[:neumann]`.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/thermal.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math/data)."
  )

(defn new-field
  [nx ny h alpha ambient t-melt]
  (let [nx (max nx 3) ny (max ny 3)]
    {:nx nx :ny ny :h h :alpha alpha :ambient ambient :t-melt t-melt
     :rho-c 4.0e6 :h-conv 0.0
     :t (vec (repeat (* nx ny) ambient))
     :peak (vec (repeat (* nx ny) ambient))
     :bc [[:neumann] [:neumann] [:neumann] [:neumann]]}))

(defn with-bc [field bc] (assoc field :bc bc))
(defn with-rho-c [field rho-c] (assoc field :rho-c rho-c))
(defn with-convection [field k] (assoc field :h-conv (max k 0.0)))

(defn idx [{:keys [nx]} i j] (+ (* j nx) i))
(defn temp [f i j] (nth (:t f) (idx f i j)))
(defn cell-center [{:keys [h]} i j] [(* (+ i 0.5) h) (* (+ j 0.5) h)])

(defn cfl-dt
  "The largest stable explicit timestep (2-D CFL: alpha*dt/h^2 <= 1/4)."
  [{:keys [h alpha]}]
  (/ (* 0.2 h h) (max alpha 1e-9)))

(defn- bc-val [bc interior]
  (case (first bc)
    :dirichlet (second bc)
    :neumann interior))

(defn apply-dirichlet
  "Re-apply Dirichlet boundary values exactly (also used directly by tests,
  mirroring the original Rust `fn apply_dirichlet`, which — though private
  in Rust — was reachable from the same-module `#[cfg(test)] mod tests`)."
  [{:keys [nx ny bc t] :as f}]
  (let [t (transient t)
        t (if (= (first (nth bc 0)) :dirichlet)
            (let [v (second (nth bc 0))]
              (reduce (fn [t j] (assoc! t (idx f 0 j) v)) t (range ny)))
            t)
        t (if (= (first (nth bc 1)) :dirichlet)
            (let [v (second (nth bc 1))]
              (reduce (fn [t j] (assoc! t (idx f (dec nx) j) v)) t (range ny)))
            t)
        t (if (= (first (nth bc 2)) :dirichlet)
            (let [v (second (nth bc 2))]
              (reduce (fn [t i] (assoc! t (idx f i 0) v)) t (range nx)))
            t)
        t (if (= (first (nth bc 3)) :dirichlet)
            (let [v (second (nth bc 3))]
              (reduce (fn [t i] (assoc! t (idx f i (dec ny)) v)) t (range nx)))
            t)]
    (assoc f :t (persistent! t))))

(defn step-multi
  "Advance by `dt` with several simultaneous heat sources, each a tuple
  `[sx sy power sigma]` whose Gaussian contributions superpose. Models
  multi-pass/multi-torch welding. An empty vector = pure conduction."
  [{:keys [nx ny h alpha ambient rho-c h-conv t peak bc] :as f} sources dt]
  (let [inv-h2 (/ 1.0 (* h h))
        prev t
        n (* nx ny)
        t' (transient (vec (repeat n 0.0)))
        peak' (transient peak)]
    (doseq [j (range ny) i (range nx)]
      (let [k (idx f i j)
            c (nth prev k)
            l (if (> i 0) (nth prev (idx f (dec i) j)) (bc-val (nth bc 0) c))
            r (if (< (inc i) nx) (nth prev (idx f (inc i) j)) (bc-val (nth bc 1) c))
            d (if (> j 0) (nth prev (idx f i (dec j))) (bc-val (nth bc 2) c))
            u (if (< (inc j) ny) (nth prev (idx f i (inc j))) (bc-val (nth bc 3) c))
            lap (* (- (+ l r d u) (* 4.0 c)) inv-h2)
            [cx cy] (cell-center f i j)
            q (reduce (fn [acc [sx sy power sigma]]
                        (let [two-sig2 (* 2.0 sigma sigma)
                              norm (/ power (* Math/PI two-sig2 rho-c))
                              dist2 (+ (* (- cx sx) (- cx sx)) (* (- cy sy) (- cy sy)))]
                          (+ acc (* norm (Math/exp (/ (- dist2) two-sig2))))))
                      0.0 sources)
            conv (* h-conv (- c ambient))
            next-t (max ambient (+ c (* (- (+ (* alpha lap) q) conv) dt)))]
        (assoc! t' k next-t)
        (when (> next-t (nth peak k)) (assoc! peak' k next-t))))
    (apply-dirichlet (assoc f :t (persistent! t') :peak (persistent! peak')))))

(defn step
  "Advance by `dt` with a single travelling volumetric heat source."
  [f sx sy power sigma dt]
  (step-multi f [[sx sy power sigma]] dt))

(defn max-temp [{:keys [t ambient]}] (reduce max ambient t))

(defn fused-fraction
  "Fraction of cells whose peak temperature reached fusion."
  [{:keys [peak t-melt]}]
  (/ (double (count (filter #(>= % t-melt) peak))) (count peak)))

(defn total-heat
  "Total thermal energy above ambient (proportional to sum(T - ambient))."
  [{:keys [t ambient]}]
  (reduce + (map #(- % ambient) t)))
