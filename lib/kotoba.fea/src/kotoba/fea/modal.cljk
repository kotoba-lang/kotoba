(ns kotoba.fea.modal
  "Natural-frequency (modal) free-vibration analysis for `:tet4` meshes.

  Resolves the declared-but-unimplemented `:modal` `AnalysisType` (and the
  `:mode-shape` `ResultField`) of the ported kami-cae contract: see
  `kotoba.fea.solver/analysis-types` and
  `kotoba.fea.postprocess/result-fields` — both listed modal analysis but
  computed nothing (`:mode-shape` returned zeros). This is the executable
  counterpart for the `:vibration-fatigue-and-safety` design domain: a
  structure's fundamental natural frequencies let the designer separate
  motor excitation lines from structural resonance before committing
  geometry, and a frequency response feeds the load spectrum that
  `kotoba.fea.fatigue` turns into cumulative damage.

  Free vibration solves the generalized eigenproblem (K - omega^2 M) phi
  = 0. K is the same linear-elastic stiffness the static solver assembles
  (`:tet4` constant-B, isotropic). M is the consistent mass matrix from the
  material's `:density`: for a linear tet4, int_V N_i N_j dV = V/10 (i=j)
  and V/20 (i!=j), so the element mass is rho*V*[1/10 diagonal, 1/20
  off-diagonal] on each of the 3 translational DOFs per node (row sum
  rho*V/4 and total rho*V per component — a valid consistent mass).

  Displacement (Dirichlet) boundary conditions eliminate the constrained
  DOFs; the eigenproblem is solved on the free-DOF subspace. Applied loads
  (`:force`, `:pressure`, `:temperature`, `:convection`) are rejected with
  `:unsupported-bc-type` — forced response is not free vibration, and
  silently ignoring the loads would return a meaningless answer (same
  loud-failure rule as the static solver).

  The symmetric generalized eigenproblem is reduced to standard form with
  Cholesky of M (M = L L^T, A = L^-1 K L^-T) and diagonalized by a cyclic
  symmetric-Jacobi pass. Smallest eigen-frequencies in Hz (f =
  sqrt(lambda)/(2 pi)) come back ascending, each with its mode shape
  recomposed to full node space (constrained DOFs = 0). A structure with
  rigid-body DOFs (insufficient constraints) reports near-zero frequencies
  before the elastic ones — the caller reads those as unanchored modes,
  not as design facts.

  Scope: `:tet4` only. `:beam2` (and anything else) is rejected with
  `:unsupported-element` because beam2's transverse DOFs carry no stiffness
  — a beam modal would emit artifact rigid modes. Like the rest of this
  repo this is an educational / small-mesh solver (dense matrices).

  Pure data + pure functions: no network, no I/O. Portable `.cljc`."
  (:require [kotoba.fea.solver :as solver]))

;; ---------------------------------------------------------------------------
;; dense linear algebra (square matrices stored row-major flat)
;; ---------------------------------------------------------------------------

(defn- at [m n i j] (nth m (+ (* i n) j)))
(defn- set-at [m n i j v] (assoc m (+ (* i n) j) v))
(defn- add-at [m n i j v] (update m (+ (* i n) j) + v))

(defn- cholesky-factors
  "Cholesky decomposition of symmetric positive-definite `a` (row-major,
  n x n) as A = L*L^T. Returns lower-triangular `l` (row-major, n x n).
  Throws ex-info `:type :singular-matrix` if `a` is not SPD."
  [a n]
  (reduce
   (fn [l i]
     (reduce
      (fn [l j]
        (let [sum (reduce + (map (fn [k] (* (at l n i k) (at l n j k))) (range j)))]
          (if (= i j)
            (let [diag (- (at a n i i) sum)]
              (when (<= diag 0.0)
                (throw (ex-info "singular matrix — not SPD" {:type :singular-matrix})))
              (set-at l n i i (Math/sqrt diag)))
            (let [denom (at l n j j)]
              (when (< (Math/abs denom) 1e-30)
                (throw (ex-info "singular matrix — not SPD" {:type :singular-matrix})))
              (set-at l n i j (/ (- (at a n i j) sum) denom))))))
      l
      (range (inc i))))
   (vec (repeat (* n n) 0.0))
   (range n)))

(defn- forward-substitute
  "Solve L*y = b for lower-triangular (row-major) `l`."
  [l b n]
  (reduce (fn [y i]
            (conj y (/ (- (nth b i)
                          (reduce + (map (fn [k] (* (at l n i k) (nth y k))) (range i))))
                       (at l n i i))))
          []
          (range n)))

(defn- backward-substitute
  "Solve L^T x = y, where `upper` is L transposed (rows are the columns of
  the Cholesky factor L)."
  [upper y n]
  (reduce (fn [x i]
            (assoc x i (/ (- (nth y i)
                             (reduce + (map (fn [k] (* (at upper n i k) (nth x k)))
                                            (range (inc i) n))))
                          (at upper n i i))))
          (vec (repeat n 0.0))
          (range (dec n) -1 -1)))

(defn- solve-lower-cols
  "Solve L*X = B (row-major (ncol x n) B). Returns X row-major (ncol x n).
  Column c of row-major B sits at indices (+ (* r n) c) for r = 0..n-1;
  each column solves L x = B[:,c] independently (forward substitution), and
  the solution column-vectors are transposed back into row-major X."
  [l b n ncol]
  (let [col-sols (vec (for [c (range ncol)]
                        (forward-substitute l
                                            (mapv #(nth b (+ (* % n) c)) (range n))
                                            n)))]
    (vec (apply concat
          (for [i (range n)]
            (mapv (fn [colvec] (nth colvec i)) col-sols))))))

;; M * x for row-major n x n matrix m.
(defn- matvec [m n x]
  (vec (for [i (range n)]
         (reduce + (map (fn [j] (* (at m n i j) (nth x j))) (range n))))))

(defn- standard-form
  "Given reduced K and M (row-major n x n, M SPD), return A = L^-1 K L^-T."
  [k m n]
  (let [l (cholesky-factors m n)
        c (solve-lower-cols l k n n)]
    (vec (apply concat
          (for [j (range n)]
            (let [v (backward-substitute l (vec (assoc (vec (repeat n 0.0)) j 1.0)) n)]
              (matvec c n v)))))))

;; ---------------------------------------------------------------------------
;; cyclic symmetric Jacobi eigensolver
;; ---------------------------------------------------------------------------

(defn- off-diag-norm [a n]
  (Math/sqrt (reduce + (for [i (range n) j (range n) :when (not= i j)]
                         (* (at a n i j) (at a n i j))))))

(defn- rotation-terms
  "c, s for the Jacobi rotation zeroing a[p][q] in plane (p,q)."
  [app aqq apq]
  (let [tau (/ (- aqq app) (* 2.0 apq))
        sg (if (pos? tau) 1.0 -1.0)
        t (/ sg (+ (Math/abs tau) (Math/sqrt (+ 1.0 (* tau tau)))))
        c (/ 1.0 (Math/sqrt (+ 1.0 (* t t))))
        s (* t c)]
    {:c c :s s}))

(defn- jacobi-rotate
  "Rotate plane (p,q) of symmetric `a` and eigenvector accumulator `v` to
  zero a[p][q]. Returns [a' v']."
  [a v n p q]
  (let [app (at a n p p) aqq (at a n q q) apq (at a n p q)
        {:keys [c s]} (rotation-terms app aqq apq)
        a1 (reduce
            (fn [a k]
              (if (or (= k p) (= k q))
                a
                (let [akp (at a n k p) akq (at a n k q)
                      akp' (- (* c akp) (* s akq))
                      akq' (+ (* s akp) (* c akq))]
                  (-> a
                      (set-at n k p akp')
                      (set-at n p k akp')
                      (set-at n k q akq')
                      (set-at n q k akq')))))
            a
            (range n))
        a2 (-> a1
               (set-at n p p (+ (- (* c c app) (* 2.0 s c apq)) (* s s aqq)))
               (set-at n q q (+ (* s s app) (* 2.0 s c apq) (* c c aqq)))
               (set-at n p q 0.0)
               (set-at n q p 0.0))
        v1 (reduce
            (fn [v k]
              (let [vkp (at v n k p) vkq (at v n k q)]
                (-> v
                    (set-at n k p (- (* c vkp) (* s vkq)))
                    (set-at n k q (+ (* s vkp) (* c vkq))))))
            v
            (range n))]
    [a2 v1]))

(defn jacobi-eigensystem
  "Cyclic symmetric Jacobi. `a` row-major n x n symmetric; returns
  {:eigenvalues [...] :eigenvectors [...]} — eigenvalues ascending, each
  eigenvector a unit column of length n. `max-sweeps` bounds the cyclic
  passes; a sweep stops early when the off-diagonal Frobenius norm drops
  below `tolerance`. `a` is scaled by its largest-magnitude entry first so
  `tolerance` is meaningful across material/stiffness scales. Pure."
  ([a n] (jacobi-eigensystem a n 1e-15 200))
  ([a n tolerance max-sweeps]
   (let [scale (reduce max (map Math/abs a))
         a (if (zero? scale) a (mapv #(/ % scale) a))
         v0 (vec (for [i (range n) j (range n)] (if (= i j) 1.0 0.0)))]
     (loop [a a v v0 sweep 0]
       (if (or (>= sweep max-sweeps) (< (off-diag-norm a n) tolerance))
         (let [pairs (sort-by first
                              (map (fn [i] [(at a n i i)
                                            (mapv #(at v n i %) (range n))])
                                   (range n)))]
           {:eigenvalues (mapv (fn [[e _]] (* e scale)) pairs)
            :eigenvectors (mapv second pairs)})
         (let [updated
               (reduce (fn [[a v] [p q]]
                         (if (< (Math/abs (at a n p q)) 1e-30)
                           [a v]
                           (jacobi-rotate a v n p q)))
                       [a v]
                       (for [p (range n) q (range (inc p) n)] [p q]))]
           (recur (nth updated 0) (nth updated 1) (inc sweep))))))))

;; ---------------------------------------------------------------------------
;; mass matrix (tet4 consistent)
;; ---------------------------------------------------------------------------

(defn tet4-mass-element
  "Consistent mass matrix (row-major 12x12) of one `:tet4` element. For the
  linear tet4, N_i N_j integrates over the element to V/10 (i=j) and V/20
  (i!=j); each of the 3 translational DOFs of node i carries rho*V/10 on its
  diagonal and rho*V/20 coupling to node j. Requires mesh `:nodes` and
  material `:density` [kg/m^3]. Pure."
  [nodes elem density]
  (let [ids (:nodes elem)
        pos #(:position (nth nodes %))
        p0 (pos (ids 0)) p1 (pos (ids 1)) p2 (pos (ids 2)) p3 (pos (ids 3))
        v (/ (Math/abs (solver/tet4-volume p0 p1 p2 p3)) 6.0)
        diag (/ (* density v) 10.0)
        off (/ (* density v) 20.0)]
    (reduce
     (fn [m [i j]]
       (let [val (if (= i j) diag off)]
         (reduce (fn [m c]
                   (set-at m 12 (+ (* i 3) c) (+ (* j 3) c) val))
                 m (range 3))))
     (vec (repeat (* 12 12) 0.0))
     (for [i (range 4) j (range 4)] [i j]))))

(defn assemble-mass
  "Global consistent mass matrix (row-major, ndof x ndof) from `:tet4`
  elements and the material's `:density` [kg/m^3]. Public so callers can
  verify the mass summary (row sum rho*V/4, total rho*V per component)."
  [mesh density]
  (let [nodes (:nodes mesh)
        ndof (* (count nodes) 3)]
    (reduce
     (fn [m elem]
       (case (:type elem)
         :tet4
         (let [ids (:nodes elem)
               me (tet4-mass-element nodes elem density)]
           (reduce
            (fn [m [i j]]
              (let [v (at me 12 i j)]
                (if (zero? v)
                  m
                  (let [gi (nth ids (quot i 3))
                        gj (nth ids (quot j 3))
                        gdi (+ (* gi 3) (rem i 3))
                        gdj (+ (* gj 3) (rem j 3))]
                    (add-at m ndof gdi gdj v)))))
            m
            (for [i (range 12) j (range 12)] [i j])))
         (throw (ex-info "unsupported element type for modal analysis"
                         {:type :unsupported-element :element-type (:type elem)}))))
     (vec (repeat (* ndof ndof) 0.0))
     (:elements mesh))))

;; ---------------------------------------------------------------------------
;; constrained-DOF reduction and public API
;; ---------------------------------------------------------------------------

(defn- dof-components
  "Masked translational component ids (0=x,1=y,2=z) for a displacement BC,
  given its `:dof-mask` keyword set. Rotational DOFs are ignored — this
  solver has only translational DOFs."
  [dof-mask]
  (vec (for [[comp kw] [[0 :x] [1 :y] [2 :z]]
             :when (contains? dof-mask kw)]
         comp)))

(defn- constrained-boolean
  "Boolean vector (length 3*n-nodes): true where a displacement BC fixes a
  translational DOF. Throws `:node-set-not-found` for a missing set and
  `:unsupported-bc-type` for any non-displacement BC."
  [mesh bcs]
  (let [nodes (:nodes mesh)
        ndof (* (count nodes) 3)
        g (atom (vec (repeat ndof false)))]
    (doseq [bc bcs]
      (case (:type bc)
        :displacement
        (let [ids (or (get (:node-sets mesh) (:node-set bc))
                      (throw (ex-info (str "node set '" (:node-set bc) "' not found in mesh")
                                      {:type :node-set-not-found :node-set (:node-set bc)})))
              comps (dof-components (:dof-mask bc))]
          (doseq [nid ids c comps]
            (swap! g assoc (+ (* nid 3) c) true)))
        (throw (ex-info (str "unsupported boundary condition type '" (:type bc)
                             "' — modal accepts only :displacement constraints")
                        {:type :unsupported-bc-type :bc bc}))))
    @g))

(defn solve-modal
  "Natural-frequency (modal) analysis. `material` must be a `:linear-elastic`
  model with a `:density`; `bcs` must be `:displacement` only (free vibration;
  applied loads are rejected).

  Returns
    {:analysis-id \"modal-0\"
     :frequencies-hz [...]        ; ascending, f = sqrt(lambda)/(2 pi)
     :omega-1/s [...]             ; sqrt(lambda)
     :eigenvalues-raw [...]       ; lambda
     :mode-shapes [[[x y z] ...]] ; per mode, full node space (constrained DOFs 0)
     :mass-total-kg m
     :free-dofs n :constrained-dofs c
     :solver :cyclic-jacobi-standard-form}

  Fails closed with ex-info `:type` `:unsupported-element` (non tet4 element
  or non linear-elastic material), `:density-required`, `:unsupported-bc-type`,
  `:node-set-not-found`, `:no-free-dofs`, or `:singular-matrix`."
  ([mesh material bcs] (solve-modal mesh material bcs {}))
  ([mesh material bcs {:keys [max-modes max-sweeps tolerance]
                       :or {max-sweeps 200 tolerance 1e-15}}]
   (let [model (:model material)
         _ (when (not= (:type model) :linear-elastic)
             (throw (ex-info "unsupported material model for modal analysis"
                             {:type :unsupported-element})))
         density (:density model)
         _ (when (nil? density)
             (throw (ex-info "modal analysis requires material :density [kg/m^3]"
                             {:type :density-required})))
         e (:youngs-modulus model)
         nu (or (:poissons-ratio model) 0.3)
         nodes (:nodes mesh)
         n-nodes (count nodes)
         ndof (* n-nodes 3)
         _ (doseq [elem (:elements mesh)]
             (when (not= :tet4 (:type elem))
               (throw (ex-info "unsupported element type for modal analysis"
                               {:type :unsupported-element
                                :element-type (:type elem)}))))
         k (solver/assemble-stiffness mesh e nu ndof)
         m (assemble-mass mesh density)
         constrained (constrained-boolean mesh bcs)
         free (vec (for [i (range ndof) :when (not (nth constrained i))] i))
         n-free (count free)
         _ (when (zero? n-free)
             (throw (ex-info "structure fully constrained — no free DOFs for modal"
                             {:type :no-free-dofs})))
         free-fold (zipmap free (range n-free))
         kr (vec (for [i (range n-free) j (range n-free)]
                   (at k ndof (nth free i) (nth free j))))
         mr (vec (for [i (range n-free) j (range n-free)]
                   (at m ndof (nth free i) (nth free j))))
         a (standard-form kr mr n-free)
         {:keys [eigenvalues eigenvectors]}
         (jacobi-eigensystem a n-free tolerance max-sweeps)
         n-modes (if (and max-modes (pos? max-modes))
                   (min max-modes n-free)
                   n-free)
         mode-shapes
         (mapv
          (fn [y]
            (let [v (backward-substitute (cholesky-factors mr n-free) y n-free)
                  phi (mapv (fn [dof] (if (contains? free-fold dof)
                                        (nth v (free-fold dof))
                                        0.0))
                            (range ndof))]
              (vec (for [i (range n-nodes)]
                     [(nth phi (* i 3))
                      (nth phi (inc (* i 3)))
                      (nth phi (+ (* i 3) 2))]))))
          (take n-modes eigenvectors))
         omegas (mapv #(Math/sqrt (max 0.0 %)) (take n-modes eigenvalues))]
     {:analysis-id "modal-0"
      :frequencies-hz (mapv #(/ % (* 2.0 Math/PI)) omegas)
      :omega-1/s omegas
      :eigenvalues-raw (take n-modes eigenvalues)
      :mode-shapes mode-shapes
      :mass-total-kg (reduce + mr)
      :free-dofs n-free
      :constrained-dofs (- ndof n-free)
      :solver :cyclic-jacobi-standard-form})))