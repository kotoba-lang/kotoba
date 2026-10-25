(ns kotoba.fea.thermal
  "Steady-state thermal conduction FEA — scalar temperature field over the
  same mesh types the structural solver supports (`:beam2` 1-D bar and
  `:tet4` linear tetrahedron), assembled with the same dense-Cholesky path.

  This fills a declared-but-unimplemented slot: `kotoba.fea.solver` lists
  `:thermal-steady` in `analysis-types` with no solver behind it, so callers
  that need a temperature field (e.g. thermal-strain loads for the structural
  solve, or metal-hydride desorption kinetics driven by solid temperature)
  had no upstream contract to consume.

  Physical model — linear, isotropic, constant-conductivity steady conduction
  with no internal heat generation and no radiation:

    div(k grad T) = 0

  Boundary conditions (plain maps, same shapes as `kotoba.fea.boundary`):
    {:type :temperature :node-set N :value T}          prescribed temperature
    {:type :convection  :face-set F :coefficient h
                        :ambient-temp Ta}              Robin BC on tri faces

  Units (all caller-supplied, preserved verbatim):
    temperature [K], conductivity k [W/(m*K)], coefficient h [W/(m^2*K)],
    heat flow [W], flux [W/m^2], node positions [m].

  Face sets: a face is a node-index triple `[a b c]`. `:face-set` may be a
  registered name (`create-face-set`) or an inline sequence of triples.
  Convection uses the consistent (non-lumped) triangle matrix
  h*A/12 * [[2 1 1],[1 2 1],[1 1 2]] and load h*Ta*A/3 per node.

  Heat-flow recovery: `:reactions` gives, per node, the heat the constraint
  network injects (W). With no sources, steady state requires
  sum(reactions) = 0 — the acceptance invariant used in tests.

  Errors via `ex-info` with `:type` one of `:unsupported-element`
  `:no-constraints` `:node-set-not-found` `:face-set-not-found`
  `:bad-conductivity` `:singular-matrix` (from the Cholesky path).
  No network, no I/O."
  (:require [kotoba.fea.solver :as solver]
            [kotoba.fea.vec3 :as v3]))

;; ---------------------------------------------------------------------------
;; small dense helpers (1 DOF per node — temperature)
;; ---------------------------------------------------------------------------

(defn- at [m n i j] (nth m (+ (* i n) j)))
(defn- add-at [v idx x] (update v idx + x))

(defn- cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by))
   (- (* az bx) (* ax bz))
   (- (* ax by) (* ay bx))])

;; ---------------------------------------------------------------------------
;; face sets
;; ---------------------------------------------------------------------------

(defn create-face-set
  "Register a named face set on `mesh`: a sequence of node-index triples
  `[a b c]` (winding order is irrelevant — only area is used)."
  [mesh name triples]
  (assoc-in mesh [:face-sets name] (mapv vec triples)))

(defn- resolve-faces
  "Resolve a `:face-set` value: a keyword/string name looks up
  `:face-sets` on the mesh; a sequence is used inline as triples."
  [mesh face-set]
  (cond
    (or (keyword? face-set) (string? face-set))
    (or (get (:face-sets mesh) face-set)
        (throw (ex-info (str "face set '" face-set "' not found in mesh")
                        {:type :face-set-not-found :face-set face-set})))
    (sequential? face-set) (mapv vec face-set)
    :else (throw (ex-info "face-set must be a name or a sequence of node triples"
                          {:type :face-set-not-found :face-set face-set}))))

(defn- face-area
  "Triangle area [m^2] of the face (a b c) over node positions."
  [nodes [a b c]]
  (let [pa (:position (nth nodes a))
        pb (:position (nth nodes b))
        pc (:position (nth nodes c))]
    (* 0.5 (v3/length (cross (v3/sub pb pa) (v3/sub pc pa))))))

;; ---------------------------------------------------------------------------
;; assembly
;; ---------------------------------------------------------------------------

(defn- assemble-beam2
  "1-D conduction along a beam2 element: ke = k*A/L. Cross-section A is the
  element's `:area` [m^2], defaulting to 1 m^2 (matching the structural
  solver's unit-section convention)."
  [k-global elem nodes k-cond ndof]
  (let [[ni nj] (:nodes elem)
        pi (:position (nth nodes ni))
        pj (:position (nth nodes nj))
        length (v3/length (v3/sub pj pi))
        area (or (:area elem) 1.0)]
    (if (< length 1e-15)
      k-global
      (let [ke (/ (* k-cond area) length)]
        (-> k-global
            (add-at (+ (* ni ndof) ni) ke)
            (add-at (+ (* nj ndof) nj) ke)
            (add-at (+ (* ni ndof) nj) (- ke))
            (add-at (+ (* nj ndof) ni) (- ke)))))))

(defn- assemble-tet4
  "3-D conduction for one linear tet4: K_ij = V * k * (grad_i . grad_j)."
  [k-global elem nodes k-cond ndof]
  (let [ids (:nodes elem)
        p (fn [i] (:position (nth nodes i)))
        [p0 p1 p2 p3] (map p ids)
        grads (solver/tet4-grads p0 p1 p2 p3)]
    (if (nil? grads)
      k-global                                        ; degenerate element, skip
      (let [V (/ (v3/abs* (solver/tet4-volume p0 p1 p2 p3)) 6.0)]
        (reduce
         (fn [k-global i]
           (reduce
            (fn [k-global j]
              (add-at k-global
                      (+ (* (nth ids i) ndof) (nth ids j))
                      (* V k-cond (v3/dot (nth grads i) (nth grads j)))))
            k-global
            (range 4)))
         k-global
         (range 4))))))

(defn- assemble-conductivity
  "Assemble the global conductivity matrix (dense, row-major, n x n) with
  one temperature DOF per node."
  [mesh k-cond ndof]
  (let [nodes (:nodes mesh)]
    (reduce
     (fn [k-global elem]
       (case (:type elem)
         :beam2 (assemble-beam2 k-global elem nodes k-cond ndof)
         :tet4  (assemble-tet4  k-global elem nodes k-cond ndof)
         (throw (ex-info "unsupported element type for the thermal solver"
                         {:type :unsupported-element :element (:type elem)}))))
     (vec (repeat (* ndof ndof) 0.0))
     (:elements mesh))))

(defn- apply-convection-bcs
  "Robin BCs: consistent triangle convection on each face of each face-set.
  Adds h*A/12*[[2 1 1] [1 2 1] [1 1 2]] to K and h*Ta*A/3 to f per face."
  [k-global f-global mesh ndof bcs]
  (let [nodes (:nodes mesh)]
    (reduce
     (fn [[k f] {:keys [face-set coefficient ambient-temp]}]
       (let [faces (resolve-faces mesh face-set)]
         (reduce
          (fn [[k f] face]
            (let [A (face-area nodes face)
                  term (* coefficient A (/ 1.0 12.0))
                  load (* coefficient ambient-temp A (/ 1.0 3.0))]
              [(reduce (fn [k [i j]]
                         (add-at k (+ (* (nth face i) ndof) (nth face j))
                                 (* term (if (= i j) 2.0 1.0))))
                       k
                       (for [i (range 3) j (range 3)] [i j]))
               (reduce (fn [f i] (add-at f (nth face i) load)) f (range 3))]))
          [k f]
          faces)))
     [k-global f-global]
     (filter #(= (:type %) :convection) bcs))))

(defn- resolve-node-set [mesh node-set]
  (or (get (:node-sets mesh) node-set)
      (throw (ex-info (str "node set '" node-set "' not found in mesh")
                      {:type :node-set-not-found :node-set node-set}))))

(defn- apply-temperature-bcs
  "Prescribed-temperature elimination (1 DOF per node), same scheme as the
  structural solver's displacement BCs."
  [k-global f-global mesh ndof bcs]
  (reduce
   (fn [[k f] bc]
     (if (not= (:type bc) :temperature)
       [k f]
       (let [{:keys [node-set value]} bc]
         (reduce
          (fn [[k f] d]
            (let [f' (reduce (fn [f r]
                               (if (= r d) f (update f r - (* (at k ndof r d) value))))
                             f (range ndof))
                  k' (reduce (fn [k j] (-> k (assoc (+ (* d ndof) j) 0.0)
                                           (assoc (+ (* j ndof) d) 0.0)))
                             k (range ndof))]
              [(assoc k' (+ (* d ndof) d) 1.0) (assoc f' d value)]))
          [k f]
          (resolve-node-set mesh node-set)))))
   [k-global f-global]
   bcs))

(defn- stabilize
  "Give unconstrained zero-conductance DOFs a unit diagonal so the matrix is
  not singular (mirrors the structural solver)."
  [k-global ndof]
  (reduce
   (fn [k d]
     (if (< (v3/abs* (at k ndof d d)) 1e-30)
       (assoc k (+ (* d ndof) d) 1.0)
       k))
   k-global
   (range ndof)))

;; ---------------------------------------------------------------------------
;; solve + recovery
;; ---------------------------------------------------------------------------

(defn- element-flux
  "Per-element flux recovery. beam2: `{:flux q :heat-flow q*A}` with axial
  q [W/m^2] positive along i->j when T_i > T_j (Fourier sign, q = -k dT/dx);
  tet4: `{:flux [qx qy qz] :heat-flow nil}` with q = -k*grad T."
  [elem nodes temperature conductivity]
  (case (:type elem)
    :beam2
    (let [[ni nj] (:nodes elem)
          pi (:position (nth nodes ni))
          pj (:position (nth nodes nj))
          L (v3/length (v3/sub pj pi))
          area (or (:area elem) 1.0)
          q (/ (* conductivity (- (nth temperature ni) (nth temperature nj))) L)]
      {:flux q :heat-flow (* q area)})
    :tet4
    (let [ids (:nodes elem)
          [p0 p1 p2 p3] (map #(:position (nth nodes %)) ids)
          grads (solver/tet4-grads p0 p1 p2 p3)]
      (if (nil? grads)
        {:flux [0.0 0.0 0.0] :heat-flow nil}
        (let [grad-T (reduce (fn [acc i]
                               (v3/add acc (v3/scale (nth grads i)
                                                     (nth temperature (nth ids i)))))
                             [0.0 0.0 0.0]
                             (range 4))]
          ;; q = -k * grad T
          {:flux (v3/scale grad-T (- conductivity)) :heat-flow nil})))))

(defn solve-thermal-steady
  "Solve steady conduction. `conductivity` is the isotropic k [W/(m*K)]
  (scalar; take material provenance from `kotoba.fea.material` presets,
  e.g. Aluminum-6061 = 167.0). Returns
    {:analysis-id :temperature :flux :heat-flow :reactions
     :max-temperature :min-temperature}
  where `:temperature` is K per node, `:flux` is per element (beam2: axial
  scalar [W/m^2]; tet4: [qx qy qz] [W/m^2]), `:heat-flow` per beam2 element
  [W] (nil for tet4), and `:reactions` is the constraint-injected heat per
  node [W] (sum ≈ 0 in steady state with no sources)."
  [mesh conductivity bcs]
  (when-not (and (number? conductivity) (pos? conductivity))
    (throw (ex-info "conductivity must be a positive number [W/(m*K)]"
                    {:type :bad-conductivity :conductivity conductivity})))
  (when-not (some #(= (:type %) :temperature) bcs)
    (throw (ex-info "no prescribed-temperature boundary conditions — problem is singular"
                    {:type :no-constraints})))
  (let [nodes (:nodes mesh)
        ndof (count nodes)
        k0 (assemble-conductivity mesh conductivity ndof)
        f0 (vec (repeat ndof 0.0))
        [k1 f1] (apply-convection-bcs k0 f0 mesh ndof bcs)
        [k2 f2] (apply-temperature-bcs k1 f1 mesh ndof bcs)
        k3 (stabilize k2 ndof)
        temperature (solver/cholesky-solve k3 f2 ndof)
        ;; reactions: r = K_full*T - f_full on the pre-elimination system.
        ;; Interior nodes r ~ 0; prescribed/convection nodes carry the net
        ;; heat the BC network supplies [W].
        reactions (vec (for [i (range ndof)]
                         (- (reduce + (for [j (range ndof)]
                                        (* (at k1 ndof i j) (nth temperature j))))
                            (nth f1 i))))
        flux (mapv #(element-flux % nodes temperature conductivity)
                   (:elements mesh))]
    {:analysis-id "thermal-steady-0"
     :temperature temperature
     :flux (mapv :flux flux)
     :heat-flow (mapv :heat-flow flux)
     :reactions reactions
     :max-temperature (reduce max (nth temperature 0) temperature)
     :min-temperature (reduce min (nth temperature 0) temperature)}))
