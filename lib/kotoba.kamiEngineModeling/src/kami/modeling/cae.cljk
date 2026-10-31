(ns kami.modeling.cae
  "Solver-neutral CAE study data and a small, independently checkable 1D linear
  static reference solver. Results carry complete provenance and qualification."
  (:require [kotoba.lang.text :as string]
            [kami.modeling.document :as document]
            [num.array :as num-array] [num.protocol :as num-protocol]
            [num.solver :as num-solver] [num.sparse :as num-sparse]))

(def analysis-kinds #{:linear-static :steady-thermal :modal})
(def qualification-levels #{:experimental :verified :qualified})
(defn- absolute [x] (#?(:clj Math/abs :cljs js/Math.abs) x))
(defn- square-root [x] (#?(:clj Math/sqrt :cljs js/Math.sqrt) x))

(defn isotropic-material [id {:keys [name youngs-modulus poisson-ratio density thermal-conductivity]}]
  (when-not (and (uuid? id) (seq name) (number? youngs-modulus) (pos? youngs-modulus)
                 (number? poisson-ratio) (< -1 poisson-ratio 0.5)
                 (or (nil? density) (pos? density))
                 (or (nil? thermal-conductivity) (pos? thermal-conductivity)))
    (throw (ex-info "invalid isotropic material" {:id id})))
  {:material/id id :material/name name :material/model :linear-isotropic
   :material/youngs-modulus youngs-modulus :material/poisson-ratio poisson-ratio
   :material/density density :material/thermal-conductivity thermal-conductivity})

(defn bar-mesh [length area elements]
  (when-not (and (number? length) (pos? length) (number? area) (pos? area)
                 (integer? elements) (pos? elements))
    (throw (ex-info "invalid bar mesh" {:length length :area area :elements elements})))
  (let [dx (/ length elements)]
    {:mesh/kind :bar-1d :mesh/length length :mesh/area area
     :mesh/nodes (mapv #(* dx %) (range (inc elements)))
     :mesh/elements (mapv vector (range elements) (range 1 (inc elements)))
     :mesh/units {:length :m :area :m2}}))

(defn study [id source-revision kind mesh material boundary-conditions loads adapter]
  (when-not (and (uuid? id) (string? source-revision) (analysis-kinds kind)
                 (map? mesh) (uuid? (:material/id material))
                 (seq boundary-conditions) (or (= kind :modal) (seq loads))
                 (string? (:adapter/id adapter)) (string? (:adapter/version adapter)))
    (throw (ex-info "invalid CAE study" {:id id :kind kind})))
  {:study/id id :study/source-revision source-revision :study/kind kind
   :study/mesh mesh :study/material material :study/boundary-conditions (vec boundary-conditions)
   :study/loads (vec loads) :study/adapter adapter :study/units :si})

(defn fixed-displacement [node value]
  (when-not (and (integer? node) (number? value)) (throw (ex-info "invalid displacement BC" {})))
  {:bc/kind :displacement :bc/node node :bc/value value})
(defn nodal-force [node value]
  (when-not (and (integer? node) (number? value)) (throw (ex-info "invalid nodal force" {})))
  {:load/kind :force :load/node node :load/value value})

(defn fixed-temperature [node value]
  (when-not (and (integer? node) (number? value)) (throw (ex-info "invalid temperature BC" {})))
  {:bc/kind :temperature :bc/node node :bc/value value})

(defn nodal-heat [node value]
  (when-not (and (integer? node) (number? value)) (throw (ex-info "invalid nodal heat load" {})))
  {:load/kind :heat :load/node node :load/value value})

(defn truss-mesh-2d [nodes elements]
  (when-not (and (<= 2 (count nodes))
                 (every? #(and (= 2 (count %)) (every? number? %)) nodes)
                 (seq elements)
                 (every? #(and (integer? (:element/a %)) (integer? (:element/b %))
                               (not= (:element/a %) (:element/b %))
                               (< -1 (:element/a %) (count nodes)) (< -1 (:element/b %) (count nodes))
                               (number? (:element/area %)) (pos? (:element/area %))) elements))
    (throw (ex-info "invalid 2D truss mesh" {})))
  {:mesh/kind :truss-2d :mesh/nodes (mapv vec nodes) :mesh/elements (vec elements)
   :mesh/units {:length :m :area :m2}})

(defn fixed-displacement-2d [node dof value]
  (when-not (and (integer? node) (#{:x :y} dof) (number? value))
    (throw (ex-info "invalid 2D displacement BC" {})))
  {:bc/kind :displacement-2d :bc/node node :bc/dof dof :bc/value value})

(defn nodal-force-2d [node [fx fy :as value]]
  (when-not (and (integer? node) (= 2 (count value)) (every? number? value))
    (throw (ex-info "invalid 2D nodal force" {})))
  {:load/kind :force-2d :load/node node :load/value [fx fy]})

(defn- zero-matrix [n] (vec (repeat n (vec (repeat n 0.0)))))
(defn- add-at [m i j x] (update-in m [i j] + x))

(defn- assemble-bar [mesh youngs-modulus]
  (let [n (count (:mesh/nodes mesh)) area (:mesh/area mesh)]
    (reduce (fn [k [a b]]
              (let [length (- (nth (:mesh/nodes mesh) b) (nth (:mesh/nodes mesh) a))
                    stiffness (/ (* youngs-modulus area) length)]
                (-> k (add-at a a stiffness) (add-at a b (- stiffness))
                    (add-at b a (- stiffness)) (add-at b b stiffness))))
            (zero-matrix n) (:mesh/elements mesh))))

(defn- solve-dense
  "Gaussian elimination with partial pivoting; sufficient as a transparent
  reference oracle, not the production sparse solver."
  [a b tolerance]
  (let [n (count b) aug (atom (mapv #(conj (vec %1) (double %2)) a b))]
    (doseq [col (range n)]
      (let [pivot (apply max-key #(absolute (get-in @aug [% col])) (range col n))]
        (when (< (absolute (get-in @aug [pivot col])) tolerance)
          (throw (ex-info "singular CAE system" {:column col})))
        (swap! aug #(assoc % col (nth % pivot) pivot (nth % col)))
        (let [p (get-in @aug [col col])]
          (swap! aug update col #(mapv (fn [x] (/ x p)) %))
          (doseq [row (range n) :when (not= row col)]
            (let [factor (get-in @aug [row col]) pivot-row (nth @aug col)]
              (swap! aug update row #(mapv - % (mapv (fn [x] (* factor x)) pivot-row))))))))
    (mapv last @aug)))

(defn solve-linear-static-bar [study]
  (when-not (and (= :linear-static (:study/kind study)) (= :bar-1d (get-in study [:study/mesh :mesh/kind])))
    (throw (ex-info "reference solver supports linear-static bar-1d only" {})))
  (let [mesh (:study/mesh study) n (count (:mesh/nodes mesh))
        k (assemble-bar mesh (get-in study [:study/material :material/youngs-modulus]))
        forces (reduce (fn [v {:load/keys [node value]}]
                         (when-not (< -1 node n) (throw (ex-info "load node out of range" {:node node})))
                         (update v node + value)) (vec (repeat n 0.0)) (:study/loads study))
        prescribed (into {} (map (juxt :bc/node :bc/value) (:study/boundary-conditions study)))
        free (vec (remove prescribed (range n)))
        reduced-k (mapv (fn [i] (mapv #(get-in k [i %]) free)) free)
        reduced-f (mapv (fn [i] (- (nth forces i)
                                   (reduce + (map (fn [[j u]] (* (get-in k [i j]) u)) prescribed)))) free)
        free-u (solve-dense reduced-k reduced-f 1.0e-12)
        displacement (reduce (fn [v [i u]] (assoc v i u))
                             (reduce (fn [v [i u]] (assoc v i u)) (vec (repeat n 0.0)) prescribed)
                             (map vector free free-u))
        internal (mapv (fn [row] (reduce + (map * row displacement))) k)
        reactions (into {} (map (fn [i] [i (- (nth internal i) (nth forces i))]) (keys prescribed)))
        energy (* 0.5 (reduce + (map * displacement internal)))
        external-work (reduce + (map * displacement forces))]
    {:result/study (:study/id study) :result/source-revision (:study/source-revision study)
     :result/adapter (:study/adapter study) :result/qualification :verified
     :result/displacement displacement :result/reactions reactions
     :result/strain-energy energy :result/external-work external-work
     :result/balance {:applied-force (reduce + forces) :reaction-force (reduce + (vals reactions))
                      :residual (+ (reduce + forces) (reduce + (vals reactions)))}}))

(defn solve-linear-static-bar-accelerated
  "Production sparse path over an injected num IBackend (CPU/WGSL/CUDA). The
  stiffness solve stays device-resident through PCG; result semantics match the
  transparent reference solver."
  [study backend options]
  (when-not (and (= :linear-static (:study/kind study))
                 (= :bar-1d (get-in study [:study/mesh :mesh/kind]))
                 (num-protocol/backend? backend))
    (throw (ex-info "accelerated solver requires linear-static bar and num backend" {})))
  (let [mesh (:study/mesh study) n (count (:mesh/nodes mesh))
        k (assemble-bar mesh (get-in study [:study/material :material/youngs-modulus]))
        forces (reduce (fn [v {:load/keys [node value]}]
                         (when-not (< -1 node n) (throw (ex-info "load node out of range" {:node node})))
                         (update v node + value)) (vec (repeat n 0.0)) (:study/loads study))
        prescribed (into {} (map (juxt :bc/node :bc/value) (:study/boundary-conditions study)))
        free (vec (remove prescribed (range n)))
        reduced-k (mapv (fn [i] (mapv #(get-in k [i %]) free)) free)
        reduced-f (mapv (fn [i] (- (nth forces i)
                                   (reduce + (map (fn [[j u]] (* (get-in k [i j]) u)) prescribed)))) free)
        csr (num-sparse/dense->csr (count free) (count free) (mapcat identity reduced-k))
        rhs (num-array/from-vec backend reduced-f [(count free)])
        solved (num-solver/pcg backend csr rhs options)
        free-u (num-array/->vec (:solver/x solved))
        _rhs-freed (num-protocol/-free backend (:handle rhs))
        _x-freed (num-protocol/-free backend (get-in solved [:solver/x :handle]))
        displacement (reduce (fn [v [i u]] (assoc v i u))
                             (reduce (fn [v [i u]] (assoc v i u)) (vec (repeat n 0.0)) prescribed)
                             (map vector free free-u))
        internal (mapv (fn [row] (reduce + (map * row displacement))) k)
        reactions (into {} (map (fn [i] [i (- (nth internal i) (nth forces i))]) (keys prescribed)))
        energy (* 0.5 (reduce + (map * displacement internal)))
        external-work (reduce + (map * displacement forces))]
    {:result/study (:study/id study) :result/source-revision (:study/source-revision study)
     :result/adapter (:study/adapter study) :result/qualification :verified
     :result/numerics (dissoc solved :solver/x)
     :result/displacement displacement :result/reactions reactions
     :result/strain-energy energy :result/external-work external-work
     :result/balance {:applied-force (reduce + forces) :reaction-force (reduce + (vals reactions))
                      :residual (+ (reduce + forces) (reduce + (vals reactions)))}}))

(defn result-current? [study result]
  (and (= (:study/id study) (:result/study result))
       (= (:study/source-revision study) (:result/source-revision result))
       (= (:study/adapter study) (:result/adapter result))))

(defn solve-linear-static-truss-2d [study]
  (when-not (and (= :linear-static (:study/kind study)) (= :truss-2d (get-in study [:study/mesh :mesh/kind])))
    (throw (ex-info "truss solver requires linear-static truss-2d" {})))
  (let [mesh (:study/mesh study) nodes (:mesh/nodes mesh) dof-count (* 2 (count nodes))
        youngs (get-in study [:study/material :material/youngs-modulus])
        k (reduce (fn [matrix {:element/keys [a b area]}]
                    (let [[ax ay] (nth nodes a) [bx by] (nth nodes b) dx (- bx ax) dy (- by ay)
                          length (square-root (+ (* dx dx) (* dy dy))) c (/ dx length) s (/ dy length)
                          factor (/ (* youngs area) length)
                          local (mapv #(mapv (fn [v] (* factor v)) %)
                                      [[(* c c) (* c s) (- (* c c)) (- (* c s))]
                                       [(* c s) (* s s) (- (* c s)) (- (* s s))]
                                       [(- (* c c)) (- (* c s)) (* c c) (* c s)]
                                       [(- (* c s)) (- (* s s)) (* c s) (* s s)]])
                          ids [(* 2 a) (inc (* 2 a)) (* 2 b) (inc (* 2 b))]]
                      (reduce (fn [m [i j]] (add-at m (nth ids i) (nth ids j) (get-in local [i j])))
                              matrix (for [i (range 4) j (range 4)] [i j]))))
                  (zero-matrix dof-count) (:mesh/elements mesh))
        forces (reduce (fn [v {:load/keys [node value]}]
                         (-> v (update (* 2 node) + (first value)) (update (inc (* 2 node)) + (second value))))
                       (vec (repeat dof-count 0.0)) (:study/loads study))
        dof-index (fn [{:bc/keys [node dof]}] (+ (* 2 node) (if (= dof :x) 0 1)))
        prescribed (into {} (map (fn [bc] [(dof-index bc) (:bc/value bc)]) (:study/boundary-conditions study)))
        free (vec (remove prescribed (range dof-count)))
        reduced-k (mapv (fn [i] (mapv #(get-in k [i %]) free)) free)
        reduced-f (mapv (fn [i] (- (nth forces i)
                                   (reduce + (map (fn [[j u]] (* (get-in k [i j]) u)) prescribed)))) free)
        free-u (solve-dense reduced-k reduced-f 1.0e-12)
        displacement (reduce (fn [v [i u]] (assoc v i u))
                             (reduce (fn [v [i u]] (assoc v i u)) (vec (repeat dof-count 0.0)) prescribed)
                             (map vector free free-u))
        internal (mapv (fn [row] (reduce + (map * row displacement))) k)
        reactions (into {} (map (fn [i] [i (- (nth internal i) (nth forces i))]) (keys prescribed)))
        element-results (mapv (fn [{:element/keys [a b area]}]
                                (let [[ax ay] (nth nodes a) [bx by] (nth nodes b) dx (- bx ax) dy (- by ay)
                                      length (square-root (+ (* dx dx) (* dy dy))) c (/ dx length) s (/ dy length)
                                      ua [(nth displacement (* 2 a)) (nth displacement (inc (* 2 a)))]
                                      ub [(nth displacement (* 2 b)) (nth displacement (inc (* 2 b)))]
                                      extension (+ (* c (- (first ub) (first ua))) (* s (- (second ub) (second ua))))
                                      strain (/ extension length) stress (* youngs strain)]
                                  {:element/strain strain :element/stress stress :element/axial-force (* stress area)}))
                              (:mesh/elements mesh))]
    {:result/study (:study/id study) :result/source-revision (:study/source-revision study)
     :result/adapter (:study/adapter study) :result/qualification :verified
     :result/displacement-2d (mapv vec (partition 2 displacement)) :result/reactions reactions
     :result/elements element-results
     :result/balance {:applied [(reduce + (take-nth 2 forces)) (reduce + (take-nth 2 (rest forces)))]
                      :reaction [(reduce + (map #(get reactions % 0) (range 0 dof-count 2)))
                                 (reduce + (map #(get reactions % 0) (range 1 dof-count 2)))]}}))

(defn analytic-bar-displacement [force length youngs-modulus area]
  (/ (* force length) (* youngs-modulus area)))

(defn solve-steady-thermal-bar [study]
  (when-not (and (= :steady-thermal (:study/kind study)) (= :bar-1d (get-in study [:study/mesh :mesh/kind])))
    (throw (ex-info "thermal reference solver supports steady-thermal bar-1d only" {})))
  (let [mesh (:study/mesh study) n (count (:mesh/nodes mesh)) area (:mesh/area mesh)
        conductivity (get-in study [:study/material :material/thermal-conductivity])]
    (when-not (and (number? conductivity) (pos? conductivity))
      (throw (ex-info "thermal study requires positive conductivity" {})))
    (let [k (reduce (fn [matrix [a b]]
                      (let [length (- (nth (:mesh/nodes mesh) b) (nth (:mesh/nodes mesh) a))
                            conductance (/ (* conductivity area) length)]
                        (-> matrix (add-at a a conductance) (add-at a b (- conductance))
                            (add-at b a (- conductance)) (add-at b b conductance))))
                    (zero-matrix n) (:mesh/elements mesh))
          heat (reduce (fn [v {:load/keys [node value]}] (update v node + value))
                       (vec (repeat n 0.0)) (:study/loads study))
          prescribed (into {} (map (juxt :bc/node :bc/value) (:study/boundary-conditions study)))
          free (vec (remove prescribed (range n)))
          reduced-k (mapv (fn [i] (mapv #(get-in k [i %]) free)) free)
          reduced-q (mapv (fn [i] (- (nth heat i)
                                     (reduce + (map (fn [[j t]] (* (get-in k [i j]) t)) prescribed)))) free)
          free-temperature (if (seq free) (solve-dense reduced-k reduced-q 1.0e-12) [])
          temperature (reduce (fn [v [i t]] (assoc v i t))
                              (reduce (fn [v [i t]] (assoc v i t)) (vec (repeat n 0.0)) prescribed)
                              (map vector free free-temperature))
          internal (mapv (fn [row] (reduce + (map * row temperature))) k)
          reactions (into {} (map (fn [i] [i (- (nth internal i) (nth heat i))]) (keys prescribed)))
          residual (+ (reduce + heat) (reduce + (vals reactions)))
          fluxes (mapv (fn [[a b]]
                         (let [length (- (nth (:mesh/nodes mesh) b) (nth (:mesh/nodes mesh) a))]
                           (* (- conductivity) (/ (- (nth temperature b) (nth temperature a)) length))))
                       (:mesh/elements mesh))]
      {:result/study (:study/id study) :result/source-revision (:study/source-revision study)
       :result/adapter (:study/adapter study) :result/qualification :verified
       :result/temperature temperature :result/heat-reactions reactions :result/heat-flux fluxes
       :result/balance {:applied-heat (reduce + heat) :reaction-heat (reduce + (vals reactions))
                        :residual residual}})))

(defn analytic-bar-temperature [fixed-temperature heat length conductivity area x]
  (+ fixed-temperature (/ (* heat x) (* conductivity area))))

(defn solve-modal-bar [study iterations]
  (when-not (and (= :modal (:study/kind study)) (= :bar-1d (get-in study [:study/mesh :mesh/kind]))
                 (integer? iterations) (pos? iterations))
    (throw (ex-info "modal solver requires modal bar-1d and positive iterations" {})))
  (let [mesh (:study/mesh study) n (count (:mesh/nodes mesh)) area (:mesh/area mesh)
        youngs (get-in study [:study/material :material/youngs-modulus])
        density (get-in study [:study/material :material/density])]
    (when-not (and (number? density) (pos? density)) (throw (ex-info "modal study requires density" {})))
    (let [k (assemble-bar mesh youngs)
          mass (reduce (fn [matrix [a b]]
                         (let [length (- (nth (:mesh/nodes mesh) b) (nth (:mesh/nodes mesh) a))
                               factor (/ (* density area length) 6.0)]
                           (-> matrix (add-at a a (* 2 factor)) (add-at a b factor)
                               (add-at b a factor) (add-at b b (* 2 factor)))))
                       (zero-matrix n) (:mesh/elements mesh))
          fixed (set (map :bc/node (:study/boundary-conditions study)))
          free (vec (remove fixed (range n)))
          kr (mapv (fn [i] (mapv #(get-in k [i %]) free)) free)
          mr (mapv (fn [i] (mapv #(get-in mass [i %]) free)) free)
          mat-vec (fn [matrix vector] (mapv #(reduce + (map * % vector)) matrix))
          mass-norm (fn [vector] (square-root (reduce + (map * vector (mat-vec mr vector)))))
          initial (vec (repeat (count free) 1.0))
          normalized (mapv #(/ % (mass-norm initial)) initial)
          mode (loop [x normalized i 0]
                 (if (= i iterations) x
                   (let [rhs (mat-vec mr x) y (solve-dense kr rhs 1.0e-14) norm (mass-norm y)]
                     (recur (mapv #(/ % norm) y) (inc i)))))
          kx (mat-vec kr mode) mx (mat-vec mr mode)
          eigenvalue (/ (reduce + (map * mode kx)) (reduce + (map * mode mx)))
          omega (square-root eigenvalue) frequency (/ omega (* 2 #?(:clj Math/PI :cljs js/Math.PI)))
          full-mode (reduce (fn [v [node value]] (assoc v node value)) (vec (repeat n 0.0)) (map vector free mode))]
      {:result/study (:study/id study) :result/source-revision (:study/source-revision study)
       :result/adapter (:study/adapter study) :result/qualification :verified
       :result/modes [{:mode/index 1 :mode/eigenvalue eigenvalue :mode/angular-frequency omega
                       :mode/frequency-hz frequency :mode/shape full-mode}]
       :result/iterations iterations})))

(defn analytic-fixed-free-bar-frequency [length youngs density]
  (/ (square-root (/ youngs density)) (* 4 length)))

(defn convergence-report [solutions]
  (when (< (count solutions) 2) (throw (ex-info "convergence needs at least two solutions" {})))
  (let [tips (mapv #(last (:result/displacement %)) solutions)
        differences (mapv #(absolute (- %2 %1)) tips (rest tips))
        scale (max 1.0e-30 (apply max (map absolute tips)))
        tolerance (max 1.0e-12 (* scale 1.0e-9))]
    {:convergence/tip-values tips :convergence/differences differences
     :convergence/max-difference (apply max differences) :convergence/tolerance tolerance
     :convergence/converged? (or (every? #(<= % tolerance) differences)
                                 (every? true? (map >= differences (rest differences))))}))

(defn tetra-mesh-3d [nodes elements]
  (when-not (and (<= 4 (count nodes))
                 (every? #(and (= 3 (count %)) (every? number? %)) nodes)
                 (seq elements)
                 (every? (fn [element]
                           (and (= 4 (count (:element/nodes element)))
                                (= 4 (count (distinct (:element/nodes element))))
                                (every? (fn [i] (< -1 i (count nodes))) (:element/nodes element))))
                         elements))
    (throw (ex-info "invalid tetrahedral mesh" {})))
  {:mesh/kind :tetra-3d :mesh/nodes (mapv vec nodes) :mesh/elements (vec elements)
   :mesh/units {:length :m}})

(defn fixed-displacement-3d [node dof value]
  (when-not (and (integer? node) (#{:x :y :z} dof) (number? value))
    (throw (ex-info "invalid 3D displacement BC" {})))
  {:bc/kind :displacement-3d :bc/node node :bc/dof dof :bc/value value})

(defn nodal-force-3d [node value]
  (when-not (and (integer? node) (= 3 (count value)) (every? number? value))
    (throw (ex-info "invalid 3D nodal force" {})))
  {:load/kind :force-3d :load/node node :load/value (vec value)})

(defn- transpose [m] (apply mapv vector m))
(defn- matrix-multiply [a b]
  (let [bt (transpose b)] (mapv (fn [row] (mapv #(reduce + (map * row %)) bt)) a)))
(defn- matrix-scale [m factor] (mapv #(mapv (fn [x] (* factor x)) %) m))

(defn- tetra-data [nodes [n0 n1 n2 n3]]
  (let [points (mapv nodes [n0 n1 n2 n3])
        interpolation (mapv (fn [[x y z]] [1.0 x y z]) points)
        coefficients (mapv (fn [i] (solve-dense interpolation
                                                (mapv #(if (= i %) 1.0 0.0) (range 4)) 1.0e-14)) (range 4))
        gradients (mapv #(subvec % 1 4) coefficients)
        [p0 p1 p2 p3] points a (mapv - p1 p0) b (mapv - p2 p0) c (mapv - p3 p0)
        determinant (reduce + (map * a [( - (* (b 1) (c 2)) (* (b 2) (c 1)))
                                        (- (* (b 2) (c 0)) (* (b 0) (c 2)))
                                        (- (* (b 0) (c 1)) (* (b 1) (c 0))) ]))
        volume (/ (absolute determinant) 6.0)]
    (when (< volume 1.0e-15) (throw (ex-info "degenerate tetrahedron" {:nodes [n0 n1 n2 n3]})))
    {:gradients gradients :volume volume}))

(defn- strain-matrix [gradients]
  (reduce (fn [b [i [dx dy dz]]]
            (let [column (* 3 i)]
              (-> b
                  (assoc-in [0 column] dx) (assoc-in [1 (inc column)] dy) (assoc-in [2 (+ column 2)] dz)
                  (assoc-in [3 column] dy) (assoc-in [3 (inc column)] dx)
                  (assoc-in [4 (inc column)] dz) (assoc-in [4 (+ column 2)] dy)
                  (assoc-in [5 column] dz) (assoc-in [5 (+ column 2)] dx))))
          (vec (repeat 6 (vec (repeat 12 0.0)))) (map-indexed vector gradients)))

(defn- elasticity-3d [youngs poisson]
  (let [lambda (/ (* youngs poisson) (* (+ 1 poisson) (- 1 (* 2 poisson))))
        mu (/ youngs (* 2 (+ 1 poisson))) normal (+ lambda (* 2 mu))]
    [[normal lambda lambda 0 0 0] [lambda normal lambda 0 0 0] [lambda lambda normal 0 0 0]
     [0 0 0 mu 0 0] [0 0 0 0 mu 0] [0 0 0 0 0 mu]]))

(defn solve-linear-static-tetra-3d [study]
  (when-not (and (= :linear-static (:study/kind study)) (= :tetra-3d (get-in study [:study/mesh :mesh/kind])))
    (throw (ex-info "tetra solver requires linear-static tetra-3d" {})))
  (let [mesh (:study/mesh study) nodes (:mesh/nodes mesh) dof-count (* 3 (count nodes))
        youngs (get-in study [:study/material :material/youngs-modulus])
        poisson (get-in study [:study/material :material/poisson-ratio]) d (elasticity-3d youngs poisson)
        element-data (mapv (fn [{:element/keys [nodes]}]
                             (let [{:keys [gradients volume]} (tetra-data (:mesh/nodes mesh) nodes)
                                   b (strain-matrix gradients) k (matrix-scale (matrix-multiply (transpose b) (matrix-multiply d b)) volume)]
                               {:nodes nodes :b b :volume volume :k k})) (:mesh/elements mesh))
        k (reduce (fn [global {:keys [nodes k]}]
                    (let [ids (mapv (fn [node] [(* 3 node) (inc (* 3 node)) (+ 2 (* 3 node))]) nodes)
                          ids (vec (mapcat identity ids))]
                      (reduce (fn [m [i j]] (add-at m (ids i) (ids j) (get-in k [i j]))) global
                              (for [i (range 12) j (range 12)] [i j]))))
                  (zero-matrix dof-count) element-data)
        forces (reduce (fn [v {:load/keys [node value]}]
                         (reduce (fn [v axis] (update v (+ (* 3 node) axis) + (nth value axis))) v (range 3)))
                       (vec (repeat dof-count 0.0)) (:study/loads study))
        axis-index {:x 0 :y 1 :z 2}
        prescribed (into {} (map (fn [{:bc/keys [node dof value]}] [(+ (* 3 node) (axis-index dof)) value])
                                 (:study/boundary-conditions study)))
        free (vec (remove prescribed (range dof-count)))
        reduced-k (mapv (fn [i] (mapv #(get-in k [i %]) free)) free)
        reduced-f (mapv (fn [i] (- (nth forces i)
                                   (reduce + (map (fn [[j u]] (* (get-in k [i j]) u)) prescribed)))) free)
        free-u (if (seq free) (solve-dense reduced-k reduced-f 1.0e-12) [])
        displacement (reduce (fn [v [i u]] (assoc v i u))
                             (reduce (fn [v [i u]] (assoc v i u)) (vec (repeat dof-count 0.0)) prescribed)
                             (map vector free free-u))
        internal (mapv (fn [row] (reduce + (map * row displacement))) k)
        reactions (into {} (map (fn [i] [i (- (nth internal i) (nth forces i))]) (keys prescribed)))
        results (mapv (fn [{:keys [nodes b volume]}]
                        (let [ids (vec (mapcat (fn [node] [(* 3 node) (inc (* 3 node)) (+ 2 (* 3 node))]) nodes))
                              ue (mapv displacement ids) strain (mapv #(reduce + (map * % ue)) b)
                              stress (mapv #(reduce + (map * % strain)) d)
                              [sx sy sz txy tyz tzx] stress
                              vm (square-root (* 0.5 (+ (* (- sx sy) (- sx sy)) (* (- sy sz) (- sy sz))
                                                        (* (- sz sx) (- sz sx)) (* 6 (+ (* txy txy) (* tyz tyz) (* tzx tzx))))))]
                          {:element/volume volume :element/strain strain :element/stress stress :element/von-mises vm})) element-data)
        component-sum (fn [values axis] (reduce + (take-nth 3 (drop axis values))))]
    {:result/study (:study/id study) :result/source-revision (:study/source-revision study)
     :result/adapter (:study/adapter study) :result/qualification :verified
     :result/displacement-3d (mapv vec (partition 3 displacement)) :result/reactions reactions :result/elements results
     :result/balance {:applied (mapv #(component-sum forces %) (range 3))
                      :reaction (mapv #(reduce + (map (fn [i] (get reactions i 0)) (range % dof-count 3))) (range 3))}}))

(defn compare-result-fields
  "Compare flattened numeric result fields from independent adapters. Both an
  absolute and relative tolerance are enforced per value."
  [candidate reference field absolute-tolerance relative-tolerance]
  (when-not (and (keyword? field) (not= (get-in candidate [:result/adapter :adapter/id])
                                         (get-in reference [:result/adapter :adapter/id]))
                 (every? #(and (number? %) (not (neg? %))) [absolute-tolerance relative-tolerance]))
    (throw (ex-info "comparison requires independent adapters and non-negative tolerances" {})))
  (let [flatten-numbers (fn flatten-numbers [x]
                          (cond (number? x) [x] (sequential? x) (mapcat flatten-numbers x) :else []))
        actual (vec (flatten-numbers (get candidate field)))
        expected (vec (flatten-numbers (get reference field)))]
    (when-not (= (count actual) (count expected))
      (throw (ex-info "result field shape mismatch" {:field field :actual (count actual) :reference (count expected)})))
    (let [samples (mapv (fn [index a e]
                          (let [absolute-error (absolute (- a e))
                                relative-error (/ absolute-error (max 1.0e-30 (absolute e)))
                                pass? (or (<= absolute-error absolute-tolerance)
                                          (<= relative-error relative-tolerance))]
                            {:sample/index index :sample/actual a :sample/reference e
                             :sample/absolute-error absolute-error :sample/relative-error relative-error
                             :sample/pass? pass?}))
                        (range) actual expected)]
      {:comparison/field field :comparison/samples samples
       :comparison/max-absolute-error (apply max 0 (map :sample/absolute-error samples))
       :comparison/max-relative-error (apply max 0 (map :sample/relative-error samples))
       :comparison/pass? (every? :sample/pass? samples)})))

(defn import-calculix-frd-displacements
  "Read the nodal DISP dataset from an ASCII CalculiX FRD result."
  [text adapter]
  (let [lines (string/split-lines text)
        [_ values]
        (reduce (fn [[reading result] line]
                  (cond
                    (string/includes? line " DISP ") [true result]
                    (and reading (re-find #"^\s*-3" line)) [false result]
                    (and reading (re-find #"^\s*-1\s+\d+" line))
                    (let [numbers (mapv parse-double (re-seq #"[-+]?\d+\.\d+E[-+]\d+" line))]
                      [reading (conj result numbers)])
                    :else [reading result])) [false []] lines)]
    (when-not (seq values) (throw (ex-info "CalculiX FRD has no displacement dataset" {})))
    {:result/adapter adapter :result/displacement-3d values
     :result/displacement (mapv first values) :result/qualification :external-reference}))

(defn qualification-manifest [study candidate reference comparisons evidence]
  (when-not (and (uuid? (:study/id study)) (seq comparisons)
                 (every? :comparison/pass? comparisons)
                 (string? (:evidence/source evidence)) (string? (:evidence/license evidence)))
    (throw (ex-info "qualification evidence is incomplete or failed" {:comparisons comparisons :evidence evidence})))
  {:qualification/schema 1 :qualification/study (:study/id study)
   :qualification/source-revision (:study/source-revision study)
   :qualification/candidate-adapter (:result/adapter candidate)
   :qualification/reference-adapter (:result/adapter reference)
   :qualification/comparisons (vec comparisons) :qualification/evidence evidence
   :qualification/status :qualified
   :qualification/revision (document/revision-id
                            {:study (:study/id study) :source (:study/source-revision study)
                             :candidate (:result/adapter candidate) :reference (:result/adapter reference)
                             :comparisons comparisons :evidence evidence})})
