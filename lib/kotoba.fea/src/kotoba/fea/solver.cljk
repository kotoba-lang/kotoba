(ns kotoba.fea.solver
  "Linear-static FEA solver — cljc port of kami-cae's `solver` module
  (kami-engine, retired per ADR-2607010000).

  Supports meshes of `:beam2` (1-D bar) and `:tet4` (4-node linear
  tetrahedron) elements. beam2 matches kami-cae's original scope exactly
  (unit cross-section A = 1 m^2, axial only); tet4 is a new addition that
  assembles a full 3-D linear-elastic element stiffness K_e = V * B^T D B
  (constant B for the linear element), letting callers solve genuine 3-D
  elasticity (bending, shear, arbitrary geometry) rather than only 1-D bars.
  `:hex8`/`:tet10`/`:tri*`/`:quad4` element assembly is still unsupported
  (declared `:unsupported-element`), matching the original kami-cae scope.

  Only translational DOFs (x, y, z per node -> 3*N total DOFs) are considered.
  Errors are reported via `ex-info` with `:type` one of `:singular-matrix`
  `:unsupported-element` `:no-loads` `:node-set-not-found`
  `:unsupported-bc-type` `:temperature-undefined`
  `:reference-temperature-required` `:thermal-expansion-missing`
  `:face-set-not-found` `:face-not-in-tet4` `:ambiguous-face`
  `:degenerate-face`. No network, no I/O.

  Thermal strain (tet4 + beam2): `:temperature` boundary conditions (the
  constructors in `kotoba.fea.boundary`) prescribe nodal temperatures.
  Together with a `:reference-temperature` option they produce an isotropic
  initial strain eps_th = alpha * (T - T_ref) [1/K, alpha from the material
  model's `:thermal-expansion`], carried as equivalent nodal forces
  f = integral B^T D eps_th dV (exact for the constant-strain tet4 / axial
  beam2) and subtracted from the mechanical strain in stress recovery
  (sigma = D (B u - eps_th)). Without `:temperature` BCs the solve is
  bit-for-bit the previous purely mechanical one.

  Surface pressure (tet4): a `:pressure` boundary condition names a face
  set (`kotoba.fea.mesh/create-face-set`, triangular faces `[a b c]` node
  ids). Uniform pressure p [Pa] (positive = pushing against the structure)
  on each boundary face of a :tet4 element is integrated exactly
  (p*A/3 per face node — constant traction, linear element) and assembled
  as nodal loads; the outward normal is taken from the element's interior
  node, so face node winding is irrelevant. A face that is not a boundary
  face of exactly one tet4 errors (`:face-not-in-tet4` / `:ambiguous-face`)
  rather than guessing a normal.

  Boundary-condition types other than `:force`/`:displacement`/
  `:temperature`/`:pressure` (`:convection`) are REJECTED loudly
  (`:unsupported-bc-type`) instead of being silently ignored — a silent
  drop would return a wrong structural answer with no error."
  (:require [kotoba.fea.vec3 :as v3]))

;; ---------------------------------------------------------------------------
;; analysis / solver method selectors (data port — see namespace docstring)
;; ---------------------------------------------------------------------------

(def analysis-types
  #{:linear-static :nonlinear-static :modal :thermal-steady :thermal-transient :buckling})

(def default-solver-method {:type :direct-cholesky})

(defn conjugate-gradient-method [max-iter tolerance]
  {:type :conjugate-gradient :max-iter max-iter :tolerance tolerance})

(def gmres-method {:type :gmres})

;; ---------------------------------------------------------------------------
;; dense linear algebra helpers (educational, small problems)
;; ---------------------------------------------------------------------------

(defn- at [m n i j] (nth m (+ (* i n) j)))

(defn- cholesky-decompose
  "Decompose symmetric positive-definite `a` (row-major, n x n) as
  A = L*L^T. Throws `ex-info` `{:type :singular-matrix}` if not SPD."
  [a n]
  (reduce
   (fn [l i]
     (reduce
      (fn [l j]
        (let [sum (reduce + (map (fn [k] (* (at l n i k) (at l n j k))) (range j)))]
          (if (= i j)
            (let [diag (- (at a n i i) sum)]
              (when (<= diag 0.0)
                (throw (ex-info "singular stiffness matrix — check constraints"
                                 {:type :singular-matrix})))
              (assoc l (+ (* i n) j) (v3/sqrt* diag)))
            (let [denom (at l n j j)]
              (when (< (v3/abs* denom) 1e-30)
                (throw (ex-info "singular stiffness matrix — check constraints"
                                 {:type :singular-matrix})))
              (assoc l (+ (* i n) j) (/ (- (at a n i j) sum) denom))))))
      l
      (range (inc i))))
   (vec (repeat (* n n) 0.0))
   (range n)))

(defn- forward-substitute
  "Solve L*y = b."
  [l b n]
  (reduce
   (fn [y i]
     (let [sum (reduce + (map (fn [k] (* (at l n i k) (nth y k))) (range i)))]
       (conj y (/ (- (nth b i) sum) (at l n i i)))))
   []
   (range n)))

(defn- backward-substitute
  "Solve L^T*x = y."
  [l y n]
  (reduce
   (fn [x i]
     (let [sum (reduce + (map (fn [k] (* (at l n k i) (nth x k))) (range (inc i) n)))]
       (assoc x i (/ (- (nth y i) sum) (at l n i i)))))
   (vec (repeat n 0.0))
   (range (dec n) -1 -1)))

(defn cholesky-solve
  "Solve a symmetric positive-definite system Ax = b via Cholesky
  decomposition. `a` is stored row-major, dimension `n x n`."
  [a b n]
  (let [l (cholesky-decompose a n)
        y (forward-substitute l b n)]
    (backward-substitute l y n)))

;; ---------------------------------------------------------------------------
;; 3-D element helpers (tet4)
;; ---------------------------------------------------------------------------

(defn- cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by))
   (- (* az bx) (* ax bz))
   (- (* ax by) (* ay bx))])

(defn- mat3-inverse
  "Inverse of a 3x3 matrix (nested rows [[a00 a01 a02] ...]). Returns the
  inverse as nested rows, or nil if (near-)singular."
  [[[a00 a01 a02] [a10 a11 a12] [a20 a21 a22]]]
  (let [det (+ (* a00 (- (* a11 a22) (* a12 a21)))
               (* a01 (- (* a12 a20) (* a10 a21)))
               (* a02 (- (* a10 a21) (* a11 a20))))]
    (when (> (v3/abs* det) 1e-30)
      (let [inv-det (/ 1.0 det)]
        [[(* inv-det (- (* a11 a22) (* a12 a21)))
          (* inv-det (- (* a02 a21) (* a01 a22)))
          (* inv-det (- (* a01 a12) (* a02 a11)))]
         [(* inv-det (- (* a12 a20) (* a10 a22)))
          (* inv-det (- (* a00 a22) (* a02 a20)))
          (* inv-det (- (* a02 a10) (* a00 a12)))]
         [(* inv-det (- (* a10 a21) (* a11 a20)))
          (* inv-det (- (* a01 a20) (* a00 a21)))
          (* inv-det (- (* a00 a11) (* a01 a10)))]]))))

(defn tet4-volume
   "Signed volume*6 of tetrahedron p0..p3 (scalar triple product of the three
   edge vectors from p0). |result|/6 is the element volume. Public so the
   thermal solver can reuse the same geometry kernel."
   [p0 p1 p2 p3]
  (v3/dot (v3/sub p1 p0) (cross (v3/sub p2 p0) (v3/sub p3 p0))))

(defn tet4-grads
  "Shape-function gradients dN_i/d(xyz) for tet4 nodes p0..p3. Returns a
   vector of 4 gradients [[gx gy gz] ...]. D = [p1-p0, p2-p0, p3-p0] as
   columns; grad_i (i=1,2,3) = (D^-1)^T column i = D^-1 row i; grad_0 is the
   negative sum of the other three (N0 = 1 - N1 - N2 - N3). Returns nil if D
   is degenerate. Public so the thermal solver can reuse the same kernel."
   [p0 p1 p2 p3]
  (let [D [[(- (p1 0) (p0 0)) (- (p2 0) (p0 0)) (- (p3 0) (p0 0))]
           [(- (p1 1) (p0 1)) (- (p2 1) (p0 1)) (- (p3 1) (p0 1))]
           [(- (p1 2) (p0 2)) (- (p2 2) (p0 2)) (- (p3 2) (p0 2))]]
        Dinv (mat3-inverse D)]
    (when Dinv
      (let [g1 (nth Dinv 0)
            g2 (nth Dinv 1)
            g3 (nth Dinv 2)
            g0 (v3/scale (v3/add (v3/add g1 g2) g3) -1.0)]
        [g0 g1 g2 g3]))))

(defn- tet4-B
  "B matrix (6x12 row-major flat) for a linear tet4. Voigt strain order is
  [xx yy zz yz xz xy] with engineering shear (gamma). Each node i contributes
  a 3-column block [dN_i/dx dy dz]. grads = 4 gradients."
  [grads]
  (let [[g0 g1 g2 g3] grads
        [gx0 gy0 gz0] g0 [gx1 gy1 gz1] g1 [gx2 gy2 gz2] g2 [gx3 gy3 gz3] g3]
    [gx0 0   0    gx1 0   0    gx2 0   0    gx3 0   0      ; xx
     0   gy0 0    0   gy1 0    0   gy2 0    0   gy3 0      ; yy
     0   0   gz0  0   0   gz1  0   0   gz2  0   0   gz3    ; zz
     0   gz0 gy0  0   gz1 gy1  0   gz2 gy2  0   gz3 gy3   ; yz
     gz0 0   gx0  gz1 0   gx1  gz2 0   gx2  gz3 0   gx3   ; xz
     gy0 gx0 0    gy1 gx1 0    gy2 gx2 0    gy3 gx3 0]))   ; xy

(defn- isotropic-3D-D
  "Constitutive matrix D (6x6 row-major flat) for isotropic linear elasticity
  with Young's modulus E [Pa] and Poisson's ratio nu. Voigt order
  [xx yy zz yz xz xy], engineering shear."
  [E nu]
  (let [factor (/ E (* (+ 1.0 nu) (- 1.0 (* 2.0 nu))))
        d1 (* factor (- 1.0 nu))      ; diagonal normal
        d2 (* factor nu)              ; off-diagonal normal
        d3 (* factor (/ (- 1.0 (* 2.0 nu)) 2.0))] ; shear diagonal
    [d1 d2 d2 0  0  0
     d2 d1 d2 0  0  0
     d2 d2 d1 0  0  0
     0  0  0  d3 0  0
     0  0  0  0  d3 0
     0  0  0  0  0  d3]))

(defn- mat-BtDB
  "Compute B^T D B for B (6x12 row-major flat) and D (6x6 row-major flat).
  Returns the 12x12 element stiffness contribution (un-scaled by volume) as
  a row-major flat vector."
  [B D]
  (let [;; DB = D * B  (6x12)
        DB (vec (for [r (range 6) c (range 12)]
                  (reduce + (for [k (range 6)]
                              (* (at D 6 r k) (at B 12 k c))))))]
    ;; result[r][c] = sum_k B[k][r] * DB[k][c]   (B^T * DB), 12x12
    (vec (for [r (range 12) c (range 12)]
           (reduce + (for [k (range 6)]
                       (* (at B 12 k r) (at DB 12 k c))))))))

;; ---------------------------------------------------------------------------
;; assembly
;; ---------------------------------------------------------------------------

(defn- add-at [v idx x] (update v idx + x))

(defn- assemble-beam2
  "Assemble one beam2 (1-D bar) element's axial stiffness into the global
  matrix. Unit cross-section A = 1 m^2; only the along-axis direction gets
  stiffness."
  [k-global elem nodes youngs-modulus ndof]
  (let [[ni nj] (:nodes elem)
        pi (:position (nth nodes ni))
        pj (:position (nth nodes nj))
        delta (v3/sub pj pi)
        length (v3/length delta)]
    (if (< length 1e-15)
      k-global
      (let [dir (v3/scale delta (/ 1.0 length))
            ke (/ youngs-modulus length)        ; A = 1
            dofs-i [(* ni 3) (inc (* ni 3)) (+ (* ni 3) 2)]
            dofs-j [(* nj 3) (inc (* nj 3)) (+ (* nj 3) 2)]]
        (reduce
         (fn [k-global a]
           (reduce
            (fn [k-global b]
              (let [val (* ke (nth dir a) (nth dir b))
                    ii (nth dofs-i a) ib (nth dofs-i b)
                    ji (nth dofs-j a) jb (nth dofs-j b)]
                (-> k-global
                    (add-at (+ (* ii ndof) ib) val)
                    (add-at (+ (* ji ndof) jb) val)
                    (add-at (+ (* ii ndof) jb) (- val))
                    (add-at (+ (* ji ndof) ib) (- val)))))
            k-global
            (range 3)))
         k-global
         (range 3))))))

(defn- assemble-tet4
  "Assemble one tet4 (4-node linear tetrahedron) element's 3-D elastic
  stiffness K_e = V * B^T D B into the global matrix."
  [k-global elem nodes youngs-modulus poissons-ratio ndof]
  (let [ids (:nodes elem)
        p0 (:position (nth nodes (ids 0)))
        p1 (:position (nth nodes (ids 1)))
        p2 (:position (nth nodes (ids 2)))
        p3 (:position (nth nodes (ids 3)))
        grads (tet4-grads p0 p1 p2 p3)]
    (if (nil? grads)
      k-global                                        ; degenerate element, skip
      (let [V (/ (v3/abs* (tet4-volume p0 p1 p2 p3)) 6.0)
            B (tet4-B grads)
            D (isotropic-3D-D youngs-modulus poissons-ratio)
            Ke (mat-BtDB B D)                         ; 12x12 flat, un-scaled
            ;; element local DOF -> global DOF: local i -> node (quot i 3), comp (rem i 3)
            gdof (fn [i] (+ (* (nth ids (quot i 3)) 3) (rem i 3)))]
        (reduce
         (fn [k-global i]
           (reduce
            (fn [k-global j]
              (let [val (* V (at Ke 12 i j))]
                (add-at k-global (+ (* (gdof i) ndof) (gdof j)) val)))
            k-global
            (range 12)))
         k-global
         (range 12))))))

(defn assemble-stiffness
  "Assemble the global stiffness matrix (dense, row-major, ndof x ndof) from
  mesh elements. Dispatches on element :type. Public so the natural-frequency
  solver (`kotoba.fea.modal`) reuses the same linear-elastic stiffness for the
  free-vibration ((K - w^2 M)) problem instead of duplicating element assembly.
  Dispatches on element :type — :beam2 and :tet4 supported."
  [mesh youngs-modulus poissons-ratio ndof]
  (let [nodes (:nodes mesh)]
    (reduce
     (fn [k-global elem]
       (case (:type elem)
         :beam2 (assemble-beam2 k-global elem nodes youngs-modulus ndof)
         :tet4  (assemble-tet4  k-global elem nodes youngs-modulus poissons-ratio ndof)
         (throw (ex-info "unsupported element type for this solver"
                          {:type :unsupported-element}))))
     (vec (repeat (* ndof ndof) 0.0))
     (:elements mesh))))

(defn- apply-force-bcs
  "Apply :force BCs. Throws :no-loads only when there are no loads at all
  (no force AND no other load type either — a pure thermal or pure
  pressure problem legitimately carries no concentrated force)."
  ([f-global mesh bcs] (apply-force-bcs f-global mesh bcs false))
  ([f-global mesh bcs other-loads?]
   (let [force-bcs (filter #(= (:type %) :force) bcs)]
    (when (and (empty? force-bcs) (not other-loads?))
      (throw (ex-info "no force boundary conditions specified" {:type :no-loads})))
    (reduce
     (fn [f {:keys [node-set value]}]
       (let [ids (or (get (:node-sets mesh) node-set)
                      (throw (ex-info (str "node set '" node-set "' not found in mesh")
                                       {:type :node-set-not-found :node-set node-set})))
             [vx vy vz] value]
         (reduce (fn [f nid]
                    (let [base (* nid 3)]
                      (-> f (add-at base vx) (add-at (inc base) vy) (add-at (+ base 2) vz))))
                  f ids)))
     f-global
     force-bcs))))

;; ---------------------------------------------------------------------------
;; surface pressure (tet4)
;; ---------------------------------------------------------------------------

(defn tet4-face-pressure-load
  "Consistent nodal loads for uniform pressure `p` [Pa] on triangular face
  `face` `[a b c]` (node ids) of a tet4 element whose remaining (interior)
  node is `interior-id`. `nodes` is the mesh's node vector.

  Sign convention: positive `p` acts ON the face — it pushes against the
  element, i.e. the load on each face node points along the inward
  normal. For the linear tet4 the consistent load of a uniform traction
  is exact: each of the 3 face nodes carries p*A/3 along the normal
  (lumped from the element's constant-traction surface integral).

  Returns `{node-id [fx fy fz]}`. Throws `:degenerate-face` when the face
  has zero area. Pure — no I/O, portable."
  [nodes face interior-id p]
  (let [pos #(:position (nth nodes %))
        [a b c] face
        pa (pos a)
        e1 (v3/sub (pos b) pa)
        e2 (v3/sub (pos c) pa)
        n (cross e1 e2)
        area2 (v3/length n)]
    (when (< area2 1e-30)
      (throw (ex-info (str "degenerate (zero-area) face " (vec face))
                      {:type :degenerate-face :face (vec face)})))
    (let [nhat (v3/scale n (/ 1.0 area2))
          centroid (v3/scale (v3/add pa (v3/add (pos b) (pos c))) (/ 1.0 3.0))
          ;; outward = away from the element's interior node
          inward (if (pos? (v3/dot nhat (v3/sub (pos interior-id) centroid)))
                   nhat
                   (v3/scale nhat -1.0))
          ;; per-node load = -p*A/3 * outward = +p*A/3 * inward (A = |n|/2)
          f (v3/scale inward (/ (* p area2 0.5) 3.0))]
      {a f b f c f})))

(defn- tet4-elements-containing-face
  "All :tet4 elements whose node set contains every node of `face`.
  `face` must be 3 distinct node ids."
  [mesh face]
  (when-not (and (sequential? face) (= 3 (count (distinct face))))
    (throw (ex-info (str "invalid face " (vec face)
                         " — a face is 3 distinct node ids")
                    {:type :invalid-face :face (vec face)})))
  (let [nodes-set-fn (fn [elem] (set (:nodes elem)))]
    (filter (fn [elem]
              (and (= :tet4 (:type elem))
                   (every? (nodes-set-fn elem) face)))
            (:elements mesh))))

(defn- apply-pressure-bcs
  "Apply :pressure BCs (uniform pressure on named face sets) as consistent
  nodal loads. Each face must be a boundary face of exactly one :tet4
  element — an interior face shared by two elements (`:ambiguous-face`)
  or a face in no tet4 (`:face-not-in-tet4`) is an error, never a guess."
  [f-global mesh bcs]
  (let [pressure-bcs (filter #(= (:type %) :pressure) bcs)]
    (reduce
     (fn [f {:keys [face-set value]}]
       (let [faces (or (get (:face-sets mesh) face-set)
                       (throw (ex-info (str "face set '" face-set "' not found in mesh")
                                       {:type :face-set-not-found :face-set face-set})))]
         (reduce
          (fn [f face]
            (let [elems (tet4-elements-containing-face mesh face)
                  elem (case (count elems)
                         0 (throw (ex-info (str "face " (vec face) " is not part of any :tet4 element")
                                           {:type :face-not-in-tet4 :face (vec face)}))
                         1 (first elems)
                         (throw (ex-info (str "face " (vec face)
                                              " is shared by " (count elems)
                                              " :tet4 elements — only boundary faces are supported")
                                         {:type :ambiguous-face :face (vec face)})))
                  interior (some #(when-not (contains? (set face) %) %)
                                 (:nodes elem))
                  loads (tet4-face-pressure-load (:nodes mesh) face interior value)]
              (reduce-kv
               (fn [f nid fv]
                 (let [base (* nid 3)]
                   (-> f
                       (add-at base (nth fv 0))
                       (add-at (inc base) (nth fv 1))
                       (add-at (+ base 2) (nth fv 2)))))
               f
               loads)))
          f
          faces)))
     f-global
     pressure-bcs)))

(defn- apply-displacement-bcs [k-global f-global mesh ndof bcs]
   (let [masks [:x :y :z]]
    (reduce
     (fn [[k f] bc]
       (if (not= (:type bc) :displacement)
         [k f]
         (let [{:keys [node-set dof-mask value]} bc
               ids (or (get (:node-sets mesh) node-set)
                        (throw (ex-info (str "node set '" node-set "' not found in mesh")
                                         {:type :node-set-not-found :node-set node-set})))
               vals value]
           (reduce
            (fn [[k f] nid]
              (let [base (* nid 3)]
                (reduce
                 (fn [[k f] c]
                   (if (not (contains? dof-mask (nth masks c)))
                     [k f]
                     (let [d (+ base c)
                           v (nth vals c)
                           f' (reduce (fn [f r]
                                        (if (= r d) f (update f r - (* (at k ndof r d) v))))
                                      f (range ndof))
                           k' (reduce (fn [k j] (-> k (assoc (+ (* d ndof) j) 0.0)
                                                       (assoc (+ (* j ndof) d) 0.0)))
                                      k (range ndof))
                           k'' (assoc k' (+ (* d ndof) d) 1.0)
                           f'' (assoc f' d v)]
                       [k'' f''])))
                 [k f]
                 (range 3))))
            [k f]
            ids))))
     [k-global f-global]
     bcs)))

(defn- stabilize
  "Stabilise unconstrained zero-stiffness DOFs (e.g. transverse DOFs of
  bar elements with no stiffness contribution). Without this the matrix
  is singular; a tiny diagonal value effectively fixes these DOFs at
  zero without affecting other results."
  [k-global ndof]
  (let [stab 1.0]
    (reduce
     (fn [k d]
       (if (< (v3/abs* (at k ndof d d)) 1e-30)
         (assoc k (+ (* d ndof) d) stab)
         k))
     k-global
     (range ndof))))

;; ---------------------------------------------------------------------------
;; thermal strain (tet4 + beam2)
;; ---------------------------------------------------------------------------

(def supported-bc-types
  "Boundary-condition types this solver consumes. Anything else —
  including the `:convection` constructor that `kotoba.fea.boundary`
  exports for future solvers — is rejected with `:unsupported-bc-type`
  rather than silently dropped."
  #{:force :displacement :temperature :pressure})

(defn- validate-bc-types [bcs]
  (doseq [bc bcs]
    (when-not (contains? supported-bc-types (:type bc))
      (throw (ex-info (str "unsupported boundary condition type '"
                           (:type bc) "' — this solver would silently ignore it")
                      {:type :unsupported-bc-type :bc bc})))))

(defn- nodal-temperatures
  "Map node id -> prescribed temperature [K] from `:temperature` BCs.
  Node sets are resolved against the mesh; a BC naming a missing set and
  any node left without a prescribed temperature are both errors — the
  caller must prescribe the complete temperature field, never an
  assumed one."
  [mesh bcs]
  (let [temps (reduce
               (fn [t {:keys [node-set value]}]
                 (let [ids (or (get (:node-sets mesh) node-set)
                               (throw (ex-info (str "node set '" node-set "' not found in mesh")
                                               {:type :node-set-not-found :node-set node-set})))]
                   (reduce #(assoc %1 %2 value) t ids)))
               {}
               (filter #(= (:type %) :temperature) bcs))]
    (doseq [n (range (count (:nodes mesh)))]
      (when-not (contains? temps n)
        (throw (ex-info (str "node " n " has no prescribed temperature — "
                             "prescribe the complete nodal temperature field")
                        {:type :temperature-undefined :node n}))))
    temps))

(defn- mean-delta-t
  "Mean (T - T_ref) [K] over an element's nodes. Uniform per element —
  consistent with the constant-strain tet4 / axial beam2 kinematics."
  [elem temps reference-temperature]
  (/ (reduce + (map #(-> (get temps %) (- reference-temperature)) (:nodes elem)))
     (count (:nodes elem))))

(defn- tet4-thermal-force
  "Equivalent nodal force (12 flat, element-local DOF order) for a uniform
  isotropic initial strain eps_th = alpha*dT: f = V * B^T * D * eps_th.
  Exact for the linear tet4 because B is constant."
  [B D volume dT alpha]
  (let [eps-th [(* alpha dT) (* alpha dT) (* alpha dT) 0.0 0.0 0.0]
        ;; D * eps_th (6)
        de (vec (for [r (range 6)]
                  (reduce + (for [k (range 6)] (* (at D 6 r k) (nth eps-th k))))))
        ;; B^T * (D eps_th) (12)
        btde (vec (for [r (range 12)]
                    (reduce + (for [k (range 6)] (* (at B 12 k r) (nth de k))))))]
    (mapv #(* volume %) btde)))

(defn- beam2-thermal-force
  "Axial thermal nodal forces for a bar with unit cross-section:
  N_th = E*A*alpha*dT, pulling node i back / pushing node j forward
  along the unit axis (uniform free expansion, sign convention: the
  bar pushes its endpoints apart when heated)."
  [dir dT alpha youngs-modulus]
  (let [n-th (* youngs-modulus alpha dT)]     ; A = 1 m^2 (solver convention)
    {:fi (mapv #(- %) (v3/scale dir n-th))
     :fj (v3/scale dir n-th)}))

(defn- assemble-thermal-forces
  "Global thermal equivalent nodal load vector from the prescribed nodal
  temperature field. Zero vector when no temperatures are prescribed."
  [mesh temps reference-temperature youngs-modulus poissons-ratio alpha ndof]
  (if (empty? temps)
    (vec (repeat ndof 0.0))
    (let [nodes (:nodes mesh)]
      (reduce
       (fn [f elem]
         (let [dT (mean-delta-t elem temps reference-temperature)]
           (case (:type elem)
             :beam2
             (let [[ni nj] (:nodes elem)
                   dir (v3/normalize (v3/sub (:position (nth nodes nj))
                                             (:position (nth nodes ni))))
                   {:keys [fi fj]} (beam2-thermal-force dir dT alpha youngs-modulus)]
               (reduce (fn [f [dof v]] (add-at f dof v)) f
                       (concat (map vector (map #(+ (* ni 3) %) (range 3)) fi)
                               (map vector (map #(+ (* nj 3) %) (range 3)) fj))))
             :tet4
             (let [ids (:nodes elem)
                   p0 (:position (nth nodes (ids 0)))
                   p1 (:position (nth nodes (ids 1)))
                   p2 (:position (nth nodes (ids 2)))
                   p3 (:position (nth nodes (ids 3)))
                   grads (tet4-grads p0 p1 p2 p3)]
               (if (nil? grads)
                 f                                            ; degenerate: skip
                 (let [V (/ (v3/abs* (tet4-volume p0 p1 p2 p3)) 6.0)
                       B (tet4-B grads)
                       D (isotropic-3D-D youngs-modulus poissons-ratio)
                       fe (tet4-thermal-force B D V dT alpha)]
                   (reduce (fn [f i] (add-at f (+ (* (nth ids (quot i 3)) 3) (rem i 3))
                                              (nth fe i)))
                           f
                           (range 12)))))
             (throw (ex-info "unsupported element type for this solver"
                             {:type :unsupported-element})))))
       (vec (repeat ndof 0.0))
       (:elements mesh)))))

(defn solve-linear-static
  "Solve a linear-static FEA problem. `material` must have a
  `:linear-elastic` model (uses :youngs-modulus and :poissons-ratio).
  Returns `{:analysis-id :displacement :stress :strain :max-displacement
  :max-stress}` — `:displacement` is a vector of [x y z] per node.
  `:stress`/`:strain` are per-element (beam2: axial |sigma|; tet4: von Mises
  stress, with the B*D stress-recovery using the element's constant strain).

  Thermal: with `:temperature` BCs present, call the 4-arity with
  `{:reference-temperature T0}` (Kelvin, caller-supplied — never assumed).
  The material model must carry `:thermal-expansion` [1/K]. The result
  additionally carries `:thermal` `{:reference-temperature :nodal-temperature}`.

  Pressure: a `:pressure` BC names a face set (`mesh/create-face-set`);
  uniform pressure p [Pa] (positive = pushing against the structure) on
  each boundary face of a :tet4 element becomes consistent nodal loads
  (p*A/3 per face node, exact for the linear element). Boundary-condition
  types other than `:force`/`:displacement`/`:temperature`/`:pressure`
  throw `:unsupported-bc-type` (loud failure, not silent drop)."
  ([mesh material bcs]
   (solve-linear-static mesh material bcs nil))
  ([mesh material bcs {:keys [reference-temperature] :as _opts}]
   (when (not= (:type (:model material)) :linear-elastic)
     (throw (ex-info "unsupported material model for this solver" {:type :unsupported-element})))
   (validate-bc-types bcs)
   (let [youngs-modulus (:youngs-modulus (:model material))
         poissons-ratio (or (:poissons-ratio (:model material)) 0.3)
         alpha (:thermal-expansion (:model material))
         nodes (:nodes mesh)
         n-nodes (count nodes)
         ndof (* n-nodes 3)
         k0 (assemble-stiffness mesh youngs-modulus poissons-ratio ndof)
         f0 (vec (repeat ndof 0.0))
         ;; thermal field: prescribed temperatures only — absent ones error
         temps (when (some #(= (:type %) :temperature) bcs)
                 (when (nil? reference-temperature)
                   (throw (ex-info ":temperature BCs present but no :reference-temperature given"
                                   {:type :reference-temperature-required})))
                 (when (nil? alpha)
                   (throw (ex-info ":temperature BCs present but material model has no :thermal-expansion"
                                   {:type :thermal-expansion-missing})))
                 (nodal-temperatures mesh bcs))
         f1 (apply-force-bcs f0 mesh bcs
                             (or (boolean temps)
                                 (some #(= (:type %) :pressure) bcs)))
         f1p (apply-pressure-bcs f1 mesh bcs)
         f-th (if temps
                (assemble-thermal-forces mesh temps reference-temperature
                                         youngs-modulus poissons-ratio alpha ndof)
                f0)
         f1' (mapv + f1p f-th)
         [k2 f2] (apply-displacement-bcs k0 f1' mesh ndof bcs)
         k3 (stabilize k2 ndof)
         u (cholesky-solve k3 f2 ndof)
         displacement (mapv (fn [i] [(nth u (* i 3)) (nth u (inc (* i 3))) (nth u (+ (* i 3) 2))])
                            (range n-nodes))
         max-displacement (reduce max 0.0 (map v3/length displacement))
         stress-strain
         (mapv (fn [elem]
                 (case (:type elem)
                   :beam2
                   (let [[ni nj] (:nodes elem)
                         pi (:position (nth nodes ni))
                         pj (:position (nth nodes nj))
                         delta (v3/sub pj pi)
                         length (v3/length delta)
                         dir (v3/scale delta (/ 1.0 length))
                         ui (nth displacement ni)
                         uj (nth displacement nj)
                         eps (/ (v3/dot (v3/sub uj ui) dir) length)
                         ;; mechanical strain excludes the thermal initial strain
                         eps-th (if temps (* alpha (mean-delta-t elem temps reference-temperature)) 0.0)
                         sig (* youngs-modulus (- eps eps-th))]
                     {:strain eps :stress (v3/abs* sig) :mechanical-strain (- eps eps-th)})
                   :tet4
                   (let [ids (:nodes elem)
                         p0 (:position (nth nodes (ids 0)))
                         p1 (:position (nth nodes (ids 1)))
                         p2 (:position (nth nodes (ids 2)))
                         p3 (:position (nth nodes (ids 3)))
                         grads (tet4-grads p0 p1 p2 p3)]
                     (if (nil? grads)
                       {:strain 0.0 :stress 0.0}     ; degenerate element
                       (let [B (tet4-B grads)
                             D (isotropic-3D-D youngs-modulus poissons-ratio)
                             ;; element nodal displacement, 12 flat
                             u-elem (vec (mapcat #(nth displacement %) ids))
                             ;; strain = B * u  (6 voigt, constant in element)
                             eps (vec (for [r (range 6)]
                                        (reduce + (for [c (range 12)]
                                                    (* (at B 12 r c) (nth u-elem c))))))
                             eps-th (if temps
                                      (let [a (* alpha (mean-delta-t elem temps reference-temperature))]
                                        [a a a 0.0 0.0 0.0])
                                      [0.0 0.0 0.0 0.0 0.0 0.0])
                             ;; mechanical strain = total - thermal initial strain
                             eps-m (mapv - eps eps-th)
                             ;; stress = D * eps_m (6 voigt)
                             sig (vec (for [r (range 6)]
                                        (reduce + (for [c (range 6)]
                                                    (* (at D 6 r c) (nth eps-m c))))))
                             [sxx syy szz syz sxz sxy] sig
                             vm (v3/sqrt* (+ (* 0.5 (+ (* (- sxx syy) (- sxx syy))
                                                       (* (- syy szz) (- syy szz))
                                                       (* (- szz sxx) (- szz sxx))))
                                            (* 3.0 (+ (* syz syz) (* sxz sxz) (* sxy sxy)))))]
                         {:strain (first eps) :stress vm
                          ;; full 6-voigt mechanical stress — von Mises alone
                          ;; hides hydrostatic states (vm of -p*I is 0), which
                          ;; is exactly the state a fully constrained thermal
                          ;; expansion produces. Callers judging brittle-
                          ;; fracture or hydrostatic tension need the components.
                          :stress-voigt sig :mechanical-strain (first eps-m)})))))
               (:elements mesh))
         stress (mapv :stress stress-strain)
         strain (mapv :strain stress-strain)
         max-stress (reduce max 0.0 stress)
         thermal (when temps
                   {:reference-temperature reference-temperature
                    :nodal-temperature (mapv #(get temps %) (range n-nodes))})]
     (cond-> {:analysis-id "linear-static-0"
              :displacement displacement
              :stress stress
              ;; tet4 elements carry the full 6-voigt mechanical stress
              ;; (beam2 entries nil) — see the tet4 recovery note above.
              :stress-voigt (mapv :stress-voigt stress-strain)
              :strain strain
              :max-displacement max-displacement
              :max-stress max-stress}
       thermal (assoc :thermal thermal)))))
