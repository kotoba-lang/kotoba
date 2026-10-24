(ns kotoba.fea.convergence
  "Discretization-error verification for solution-vs-mesh studies.

  Downstream consumers (vehicle-designer closure, cae-solver acceptance
  gates) must carry mesh/convergence evidence with every CAE number, but
  no contract in this repo (nor in the open PR set at the time of
  writing: #1 thermal strain, #2 tet4 pressure, #3 thermal steady,
  #4 fatigue Miner, #5 probe IDW) turns a set of mesh-refined solutions
  into that evidence. This namespace is that smallest step: given three
  solutions of the SAME problem on geometrically refined meshes, it
  reports the observed convergence order, a Richardson-extrapolated
  continuum estimate, and a Grid Convergence Index (GCI) in the form
  popularized by Roache and prescribed by ASME V&V 20-2009 (§ General
  Richardson Extrapolation with constant refinement ratio).

  Inputs are CALLER-SUPPLIED measured solution values — this namespace
  invents no physical constant and no safety factor default. `:fs`
  (Roache's safety factor on the GCI, standard practice 1.25) is an
  explicit input so provenance stays with the caller.

  All math on plain scalars. No network, no I/O. Fails closed: refuses
  non-finite values, refinement ratios <= 1, non-positive mesh sizes,
  and degenerate (non-asymptotic, zero-difference) solution triplets —
  a degenerate triplet returns `:status :degenerate` rather than
  pretending an order was observed.")

(defn- finite? [x]
  #?(:clj (and (number? x) (not (Double/isNaN x)) (not (Double/isInfinite x)))
     :cljs (and (number? x) (== x x) (not= x ##Inf) (not= x (- ##Inf)))))

(defn- require-arg!
  ([cond? msg v] (when-not (cond? v) (throw (ex-info msg {:value v}))) v))

(defn observed-order
  "Observed convergence order `p` from three solution values `f1 f2 f3`
  on monotonically refined meshes with CONSTANT refinement ratio `r`
  (= h-coarse / h-fine > 1), where f1 is the FINEST-mesh value.

      p = ln |(f3 - f2) / (f2 - f1)| / ln r

  Returns `{:status :asymptotic :p p}` or `{:status :degenerate}`
  when the differences are zero (the solution is mesh-independent at
  this resolution — report it, don't divide by it). Throws on invalid
  r or non-finite values."
  [f1 f2 f3 r]
  (require-arg! finite? "convergence: solution values must be finite numbers" f1)
  (require-arg! finite? "convergence: solution values must be finite numbers" f2)
  (require-arg! finite? "convergence: solution values must be finite numbers" f3)
  (require-arg! #(and (finite? %) (> % 1.0))
                "convergence: refinement ratio r must be a number > 1" r)
  (let [d21 (- f2 f1)
        d32 (- f3 f2)]
    (if (or (zero? d21) (zero? d32))
      {:status :degenerate}
      {:status :asymptotic
       :p (/ (Math/log (Math/abs (/ d32 d21))) (Math/log r))})))

(defn richardson-extrapolate
  "Richardson estimate of the continuum (h→0) value:

      f_exact ≈ f1 + (f1 - f2) / (r^p - 1)

  where f1 is the fine-mesh value, f2 the next-coarser, `r` the same
  constant refinement ratio and `p` the observed order (e.g. from
  [[observed-order]]). Throws when `r^p` is 1 (p = 0 or invalid r) —
  a zeroth-order scheme admits no Richardson estimate."
  [f1 f2 r p]
  (require-arg! finite? "convergence: p must be a finite number" p)
  (require-arg! #(and (finite? %) (pos? %))
                "convergence: r^p must be positive" (Math/pow r p))
  (let [den (dec (Math/pow r p))]
    (when (zero? den)
      (throw (ex-info "convergence: r^p - 1 is zero; no Richardson estimate exists"
                      {:r r :p p})))
    (+ f1 (/ (- f1 f2) den))))

(defn gci-fine
  "Grid Convergence Index of the FINE mesh (Roache / ASME V&V 20):

      GCI_fine = fs · |ε| / (r^p - 1),   ε = (f2 - f1) / f1

  `fs` (Roache's safety factor, typically 1.25 for three-grid studies)
  is an explicit caller input with provenance — never defaulted here.
  Requires f1 ≠ 0 (use [[gci-fine-abs]] when the fine value is zero).
  Returns the relative (fractional) GCI; multiply by 100 for %."
  [f1 f2 r p fs]
  (require-arg! #(and (finite? %) (not (zero? %)))
                "convergence: fine-mesh value f1 must be finite and non-zero" f1)
  (require-arg! finite? "convergence: fs must be a finite number" fs)
  (let [den (dec (Math/pow r p))]
    (when (zero? den)
      (throw (ex-info "convergence: r^p - 1 is zero; GCI undefined" {:r r :p p})))
    (let [eps (/ (- f2 f1) f1)]
      (* fs (Math/abs eps) (/ den)))))

(defn convergence-study
  "Full three-grid verification report from caller-supplied
  mesh sizes and solution values:

      grids  (ordered finest → coarsest) [{:h h :value f} ...]  exactly 3
      opts   {:fs 1.25}   ; required — caller-owned safety factor

  Returns {:status :asymptotic | :degenerate
           :r :p :f-fine :f-coarse :f-extrapolated :gci-fine}

  This is the evidence record downstream consumers attach to a CAE
  number: the observed order validates the discretization, and the GCI
  bounds the discretization error of the fine solution. All failure
  modes fail closed per the namespace docstring."
  [grids {:keys [fs] :as _opts}]
  (when (or (not (sequential? grids)) (not= 3 (count grids)))
    (throw (ex-info "convergence: exactly three grids (finest first) are required"
                    {:grids grids})))
  (doseq [{:keys [h value]} grids]
    (require-arg! #(and (finite? %) (pos? %))
                  "convergence: every :h must be a positive finite number" h)
    (require-arg! finite? "convergence: every :value must be a finite number" value))
  (let [[g1 g2 g3] grids
        r (/ (:h g2) (:h g1))]
    (require-arg! #(> % 1.0)
                  "convergence: :h must strictly increase (finest grid first)" r)
    (let [f1 (:value g1) f2 (:value g2) f3 (:value g3)
          ord (observed-order f1 f2 f3 r)]
      (if (= :degenerate (:status ord))
        {:status :degenerate :r r :f-fine f1}
        (let [p (:p ord)
              fext (richardson-extrapolate f1 f2 r p)]
          {:status :asymptotic :r r :p p
           :f-fine f1 :f-coarse f2 :f-coarsest f3
           :f-extrapolated fext
           :gci-fine (gci-fine f1 f2 r p fs)})))))
