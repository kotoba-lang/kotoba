(ns cae.vv
  "Numerical verification gates for declared-scope CAE qualification.

  These checks do not certify a solver. They produce auditable evidence for a
  specifically declared model, version, benchmark, mesh family and tolerance."
  (:require [cae.solver :as solver]))

(defn- finite? [x]
  (and (number? x) #?(:clj (Double/isFinite (double x)) :cljs (js/isFinite x))))

(defn relative-error [computed reference]
  (when-not (every? finite? [computed reference])
    (throw (ex-info "relative error requires finite values" {:computed computed :reference reference})))
  (/ (abs (- (double computed) (double reference)))
     (max 1.0e-30 (abs (double reference)))))

(defn conservation-check
  "Check integral balance: inputs + sources = outputs + sinks + accumulation."
  [{:keys [inputs outputs sources sinks accumulation tolerance quantity]
    :or {sources [] sinks [] accumulation 0.0 tolerance 1.0e-8}}]
  (let [values (concat inputs outputs sources sinks [accumulation tolerance])]
    (when-not (every? finite? values)
      (throw (ex-info "conservation check requires finite values" {:values values})))
    (let [incoming (+ (reduce + 0.0 inputs) (reduce + 0.0 sources))
          outgoing (+ (reduce + 0.0 outputs) (reduce + 0.0 sinks) accumulation)
          imbalance (- incoming outgoing)
          scale (max 1.0e-30 (abs incoming) (abs outgoing))
          relative (/ (abs imbalance) scale)]
      {:check :conservation :quantity quantity :incoming incoming :outgoing outgoing
       :imbalance imbalance :relative-imbalance relative :tolerance tolerance
       :passed? (<= relative tolerance)})))

(defn residual-check
  "Require a finite residual history, final tolerance and actual reduction."
  [{:keys [history absolute-tolerance minimum-reduction]
    :or {absolute-tolerance 1.0e-8 minimum-reduction 1.0e3}}]
  (let [history (vec history)]
    (when (or (< (count history) 2) (not-every? finite? history) (some neg? history))
      (throw (ex-info "residual history needs at least two finite non-negative samples" {:history history})))
    (let [initial (first history) final (peek history)
          reduction (/ (max initial 1.0e-300) (max final 1.0e-300))]
      {:check :iterative-convergence :initial-residual initial :final-residual final
       :iterations (dec (count history)) :reduction reduction
       :absolute-tolerance absolute-tolerance :minimum-reduction minimum-reduction
       :passed? (and (<= final absolute-tolerance) (>= reduction minimum-reduction))})))

(defn grid-convergence-check
  "Three-grid Richardson verification and fine-grid GCI (constant refinement ratio)."
  [{:keys [coarse medium fine refinement-ratio gci-tolerance safety-factor]
    :or {safety-factor 1.25}}]
  (when-not (and (every? finite? [coarse medium fine refinement-ratio gci-tolerance safety-factor])
                 (> refinement-ratio 1.0) (pos? gci-tolerance))
    (throw (ex-info "invalid three-grid convergence input" {:coarse coarse :medium medium :fine fine
                                                              :refinement-ratio refinement-ratio})))
  (let [d21 (- medium fine) d32 (- coarse medium)
        monotonic? (pos? (* d21 d32))
        ratio (when (and monotonic? (not (zero? d21))) (/ (abs d32) (abs d21)))
        order (when (and ratio (pos? ratio)) (/ (Math/log ratio) (Math/log refinement-ratio)))
        denominator (when order (- (Math/pow refinement-ratio order) 1.0))
        extrapolated (when (and denominator (not (zero? denominator))) (+ fine (/ (- fine medium) denominator)))
        gci (when (and denominator (not (zero? denominator)))
              (/ (* safety-factor (abs (- fine medium)))
                 (* (max (abs fine) 1.0e-30) (abs denominator))))]
    {:check :grid-convergence :coarse coarse :medium medium :fine fine
     :refinement-ratio refinement-ratio :monotonic? monotonic? :observed-order order
     :richardson-extrapolated extrapolated :fine-grid-gci gci :gci-tolerance gci-tolerance
     :passed? (boolean (and monotonic? order (pos? order) gci (<= gci gci-tolerance)))}))

(def required-evidence-keys
  [:case-id :solver :solver-version :model-revision :input-id :mesh-id :executed-at :platform])

(defn evidence-check [evidence]
  (let [missing (vec (remove #(let [v (get evidence %)] (and (some? v) (not= "" v))) required-evidence-keys))]
    {:check :traceability :required required-evidence-keys :missing missing :evidence evidence
     :passed? (empty? missing)}))

(defn qualification-gate
  "Fail closed unless every required V&V category has passing evidence."
  [{:keys [scope checks evidence]}]
  (let [checks (conj (vec checks) (evidence-check evidence))
        required #{:analytic-benchmark :conservation :iterative-convergence :grid-convergence :traceability}
        present (set (map :check checks)) missing (vec (sort (remove present required)))
        failed (vec (remove :passed? checks)) passed? (and (map? scope) (seq scope) (empty? missing) (empty? failed))]
    {:solver :qualification-gate :scope scope :checks checks :required-checks required
     :missing-checks missing :failed-checks failed :passed? passed?
     :status (if passed? :verified-for-declared-scope :not-qualified)
     :claim (if passed? :declared-scope-only :no-industrial-accuracy-claim)}))

(defmethod solver/solve :qualification-gate [case]
  (qualification-gate case))

(defn- tridiagonal-solve [a b c d]
  (let [n (count d)
        forward (loop [i 0 cp [] dp []]
                  (if (= i n) [cp dp]
                      (let [denom (- (nth b i) (if (zero? i) 0.0 (* (nth a (dec i)) (peek cp))))
                            ci (if (= i (dec n)) 0.0 (/ (nth c i) denom))
                            di (/ (- (nth d i) (if (zero? i) 0.0 (* (nth a (dec i)) (peek dp)))) denom)]
                        (recur (inc i) (conj cp ci) (conj dp di)))))
        [cp dp] forward]
    (loop [i (dec n) x (vec (repeat n 0.0))]
      (if (neg? i) x
          (recur (dec i) (assoc x i (- (nth dp i) (* (nth cp i) (if (= i (dec n)) 0.0 (nth x (inc i)))))))))))

(defmethod solver/solve :axial-bar-fe
  [{:keys [elements length-m area-m2 youngs-modulus-Pa distributed-load-N-m]}]
  (let [n (long elements) l (double length-m) area (double area-m2) e (double youngs-modulus-Pa)
        q0 (double distributed-load-N-m)]
    (when-not (and (>= n 4) (even? n) (every? pos? [l area e q0]))
      (throw (ex-info "axial-bar FE requires even elements >=4 and positive properties" {:elements elements})))
    (let [h (/ l n) stiffness (/ (* e area) h) unknowns (dec n)
          loads (mapv (fn [i] (* h q0 (Math/sin (/ (* Math/PI i) n)))) (range 1 n))
          interior (tridiagonal-solve (vec (repeat (dec unknowns) (- stiffness)))
                                      (vec (repeat unknowns (* 2 stiffness)))
                                      (vec (repeat (dec unknowns) (- stiffness))) loads)
          u (vec (concat [0.0] interior [0.0]))
          exact-scale (/ (* q0 l l) (* e area Math/PI Math/PI))
          exact (mapv (fn [i] (* exact-scale (Math/sin (/ (* Math/PI i) n)))) (range (inc n)))
          error (Math/sqrt (/ (reduce + (map (fn [a b] (let [d (- a b)] (* d d))) u exact)) (inc n)))
          residuals (mapv (fn [i] (- (* stiffness (+ (* 2 (u i)) (- (u (dec i))) (- (u (inc i))))) (loads (dec i)))) (range 1 n))
          rhs-norm (Math/sqrt (reduce + (map #(* % %) loads)))
          residual-norm (Math/sqrt (reduce + (map #(* % %) residuals)))
          reactions [(* (- stiffness) (u 1)) (* (- stiffness) (u (dec n)))]
          applied (reduce + loads)]
      {:solver :axial-bar-fe :model :linear-fe-sinusoidal-body-load :elements n :nodes (inc n)
       :displacement-m u :midpoint-displacement-m (u (quot n 2)) :exact-midpoint-m exact-scale
       :l2-error-m error :reaction-forces-N reactions :applied-load-N applied
       :algebraic-residual-norm residual-norm :residual-history [rhs-norm residual-norm]
       :fidelity :verification-benchmark :status :computed})))

(def manufactured-solutions
  "Manufactured solutions for the 1-D bar `-EA u'' = f`, each with the source
   term derived analytically FROM the chosen `u` rather than the other way
   round. That is the whole point of the method: you do not go looking for a
   problem whose answer you happen to know, you pick the answer and compute the
   problem that has it.

   Both vanish at x=0 and x=L, so the Dirichlet conditions the assembly already
   imposes are exact. Two families rather than one, because a single sinusoid
   cannot separate a correct solver from one tuned to sinusoids — and the
   existing `:axial-bar-fe` benchmark is exactly that shape."
  {:sine {:describes "u = sin(k pi x / L)"}
   :polynomial {:describes "u = x(L-x)(x+L), a cubic no sinusoidal solver can fake"}})

(defn- mms-u [family L x k]
  (case family
    :sine (Math/sin (/ (* k Math/PI x) L))
    :polynomial (* x (- L x) (+ x L))))

(defn- mms-f
  "The source term that MAKES `mms-u` the exact solution of -EA u'' = f."
  [family L x k ea]
  (case family
    :sine (* ea (Math/pow (/ (* k Math/PI) L) 2) (Math/sin (/ (* k Math/PI x) L)))
    ;; u = x(L-x)(x+L) = L^2 x - x^3  ->  u'' = -6x  ->  f = -EA u'' = 6 EA x
    :polynomial (* 6.0 ea x)))

(defn- bar-solve
  "Nodal displacements of the fixed-fixed bar under nodal loads `h*f(x_i)`."
  [n h ea loads]
  (let [stiffness (/ ea h) unknowns (dec n)]
    (vec (concat [0.0]
                 (tridiagonal-solve (vec (repeat (dec unknowns) (- stiffness)))
                                    (vec (repeat unknowns (* 2 stiffness)))
                                    (vec (repeat (dec unknowns) (- stiffness)))
                                    loads)
                 [0.0]))))

(defmethod solver/solve :manufactured-solution
  [{:keys [family element-counts length-m area-m2 youngs-modulus-Pa wave-number
           order-tolerance]}]
  (let [fam (or family :sine)
        counts (vec (or element-counts [8 16 32 64]))
        L (double (or length-m 1.0))
        area (double (or area-m2 0.01))
        e (double (or youngs-modulus-Pa 2.0e11))
        ea (* e area)
        k (double (or wave-number 1.0))
        tol (double (or order-tolerance 0.15))]
    (when-not (contains? manufactured-solutions fam)
      (throw (ex-info "unknown manufactured solution family"
                      {:family family :known (vec (sort (keys manufactured-solutions)))})))
    (when-not (and (>= (count counts) 2)
                   (every? #(and (integer? %) (>= % 4) (even? %)) counts)
                   (every? #(= 2.0 (double %)) (map / (rest counts) counts)))
      (throw (ex-info (str "manufactured-solution needs at least two even element counts >= 4,"
                           " each twice the previous — the observed order of accuracy is read"
                           " off successive halvings of h and cannot be inferred from an"
                           " arbitrary sequence")
                      {:element-counts counts})))
    (let [runs (mapv (fn [n]
                       (let [h (/ L n)
                             xs (mapv #(* % h) (range (inc n)))
                             loads (mapv (fn [i] (* h (mms-f fam L (nth xs i) k ea))) (range 1 n))
                             uh (bar-solve n h ea loads)
                             ue (mapv #(mms-u fam L % k) xs)
                             err (Math/sqrt (/ (reduce + (map (fn [a b] (let [d (- a b)] (* d d)))
                                                              uh ue))
                                               (inc n)))]
                         {:elements n :h h :l2-error err
                          :peak-exact (reduce max (map #(Math/abs %) ue))}))
                     counts)
          peak (reduce max (map :peak-exact runs))
          ;; An order of accuracy can only be read while DISCRETISATION error
          ;; dominates. Linear elements are nodally exact for this cubic, so its
          ;; errors sit at 1e-17..1e-15 against a peak of order 1 — pure
          ;; round-off, whose ratios gave an "observed order" of -2.38. Reporting
          ;; that as a failure would call the strongest possible result the
          ;; worst one. Below the floor the answer is not a number, and saying
          ;; so is the whole discipline.
          floor (* peak 1.0e-12)
          round-off? (every? #(< (:l2-error %) floor) runs)
          orders (when-not round-off?
                   (mapv (fn [[a b]]
                           (/ (Math/log (/ (:l2-error a) (:l2-error b))) (Math/log 2.0)))
                         (partition 2 1 runs)))
          observed (when orders (peek orders))
          passed? (if round-off? true (<= (Math/abs (- observed 2.0)) tol))]
      {:solver :manufactured-solution
       :family fam
       :describes (get-in manufactured-solutions [fam :describes])
       :model :linear-fe-1d-bar
       :element-counts counts
       :runs runs
       :l2-errors (mapv :l2-error runs)
       :observed-orders orders
       :observed-order observed
       :expected-order 2.0
       :order-tolerance tol
       :round-off-floor floor
       :round-off-limited? round-off?
       :passed? passed?
       ;; The source term is derived FROM u, so a solver that is wrong in the
       ;; same way as its own benchmark cannot hide here: the error would not
       ;; fall at the rate the discretisation promises.
       :fidelity :verification-benchmark
       :status (cond round-off? :exact-to-round-off
                     passed? :computed
                     :else :order-of-accuracy-not-met)})))

(defmethod solver/solve :axial-bar-vv-study
  [{:keys [element-counts length-m area-m2 youngs-modulus-Pa distributed-load-N-m
           gci-tolerance benchmark-tolerance evidence]}]
  (let [counts (vec (or element-counts [8 16 32]))
        base {:length-m (or length-m 1.0) :area-m2 (or area-m2 0.01)
              :youngs-modulus-Pa (or youngs-modulus-Pa 2.0e11)
              :distributed-load-N-m (or distributed-load-N-m 1.0e6)}
        runs (mapv #(solver/solve (assoc base :solver {:kind :axial-bar-fe} :elements %)) counts)
        [coarse medium fine] (mapv :midpoint-displacement-m runs) fine-run (peek runs)
        reference (:exact-midpoint-m fine-run)
        analytic {:check :analytic-benchmark :computed fine :reference reference
                  :relative-error (relative-error fine reference)
                  :tolerance (or benchmark-tolerance 0.01)
                  :passed? (<= (relative-error fine reference) (or benchmark-tolerance 0.01))}
        conservation (conservation-check {:quantity :force-equilibrium :inputs [(:applied-load-N fine-run)]
                                          :outputs [(- (reduce + (:reaction-forces-N fine-run)))] :tolerance 1.0e-10})
        residual (residual-check {:history (:residual-history fine-run) :absolute-tolerance 1.0e-6
                                  :minimum-reduction 1.0e8})
        grid (grid-convergence-check {:coarse coarse :medium medium :fine fine
                                      :refinement-ratio 2.0 :gci-tolerance (or gci-tolerance 0.01)})
        checks [analytic conservation residual grid]
        gate (qualification-gate {:scope {:physics :linear-elasticity :dimension :1d
                                          :element :linear-axial :loading :sinusoidal-body-force}
                                  :checks checks :evidence evidence})]
    (assoc gate :runs runs :study {:element-counts counts :quantity :midpoint-displacement-m})))

(def release-pillars [:numerical-verification :experimental-validation :software-quality])

(defn industrial-release-gate
  "A stricter product-release gate. Numerical verification alone is never
  sufficient: independent experimental validation and software QA evidence
  must pass for the exact same declared applicability scope."
  [{:keys [scope applicability evidence] :as case}]
  (let [pillar-checks (mapv (fn [pillar]
                              (let [result (get case pillar)]
                                {:pillar pillar :result result
                                 :passed? (and (map? result) (true? (:passed? result)))}))
                            release-pillars)
        traceability (evidence-check evidence)
        applicability? (and (map? applicability)
                            (seq (:included applicability))
                            (seq (:excluded applicability)))
        passed? (and (map? scope) (seq scope) applicability?
                     (:passed? traceability) (every? :passed? pillar-checks))]
    {:solver :industrial-release-gate :scope scope :applicability applicability
     :pillars pillar-checks :traceability traceability :passed? passed?
     :status (if passed? :release-qualified-for-declared-scope :not-release-qualified)
     :claim (if passed? :declared-scope-industrial-use :no-industrial-release-claim)
     :missing-pillars (mapv :pillar (remove :passed? pillar-checks))
     :applicability-defined? (boolean applicability?)}))

(defn experimental-validation-check
  "Uncertainty-aware comparison against independent measurements.
  Passes only when normalized RMSE and the fraction inside the declared
  uncertainty envelope both satisfy explicit acceptance limits."
  [{:keys [predicted measured uncertainty normalized-rmse-limit minimum-coverage
           coverage-factor dataset-id quantity]
    :or {normalized-rmse-limit 1.0 minimum-coverage 0.95 coverage-factor 2.0}}]
  (let [predicted (vec predicted) measured (vec measured) uncertainty (vec uncertainty)]
    (when-not (and (pos? (count predicted)) (= (count predicted) (count measured) (count uncertainty))
                   (every? finite? (concat predicted measured uncertainty)) (every? pos? uncertainty))
      (throw (ex-info "experimental validation vectors must be equal, nonempty and uncertainty-positive"
                      {:predicted (count predicted) :measured (count measured) :uncertainty (count uncertainty)})))
    (let [normalized (mapv (fn [p m u] (/ (- (double p) (double m)) (double u)))
                           predicted measured uncertainty)
          nrmse (Math/sqrt (/ (reduce + (map #(* % %) normalized)) (count normalized)))
          covered (count (filter #(<= (abs %) coverage-factor) normalized))
          coverage (/ covered (double (count normalized)))
          passed? (and (<= nrmse normalized-rmse-limit) (>= coverage minimum-coverage))]
      {:check :experimental-validation :dataset-id dataset-id :quantity quantity
       :samples (count normalized) :normalized-residuals normalized
       :normalized-rmse nrmse :normalized-rmse-limit normalized-rmse-limit
       :coverage coverage :minimum-coverage minimum-coverage :coverage-factor coverage-factor
       :passed? passed? :status (if passed? :validated-for-declared-scope :validation-failed)})))

(defmethod solver/solve :industrial-release-gate [case]
  (industrial-release-gate case))
