(ns kotoba.fea.mesh
  "FEA mesh container + generators — cljc port of kami-cae's `mesh` module
  (kami-engine, retired per ADR-2607010000).

  Nodes/elements are plain Clojure data (maps/vectors) instead of the
  Rust `NodeId`/`ElementId` newtypes — node and element ids are plain
  non-negative integers, the idiomatic Clojure equivalent. Pure data +
  pure functions: no network, no I/O.

  A `mesh` is `{:nodes [...] :elements [...] :node-sets {...}
  :element-sets {...} :face-sets {...}}`. A node is `{:id int :position
  [x y z]}`. An element is `{:type kw :id int :nodes [ids...]}` — `:type`
  is one of `:beam2` `:tri3` `:tri6` `:quad4` `:tet4` `:tet10` `:hex8`,
  matching kami-cae's `FeaElement` variants (2/3/6/4/4/10/8 node
  topologies respectively). A face set maps a name to a vector of
  triangular faces, each face `[a b c]` node ids — the surface the
  solver's `:pressure` boundary condition acts on.")

(def element-orders
  "Linear (first-order) vs quadratic (second-order) elements."
  #{:linear :quadratic})

(def default-mesh-config
  "Mesh configuration for automatic meshing — mirrors kami-cae's
  `MeshConfig::default()`."
  {:element-size 1.0
   :min-size 0.1
   :max-size 10.0
   :curvature-refinement true
   :quality-threshold 0.3
   :order :linear})

(defn new-mesh [] {:nodes [] :elements [] :node-sets {} :element-sets {} :face-sets {}})

(defn add-node
  "Append a node at `position` (`[x y z]`). Returns `{:mesh mesh' :id id}`
  — kami-cae's `FeaMesh::add_node` mutates `&mut self` and returns the id;
  here the updated mesh is returned alongside the id since mesh is
  immutable."
  [mesh position]
  (let [id (count (:nodes mesh))]
    {:mesh (update mesh :nodes conj {:id id :position position})
     :id id}))

(defn add-element [mesh element] (update mesh :elements conj element))

(defn create-node-set
  "Register (or overwrite) a named node set."
  [mesh name ids]
  (assoc-in mesh [:node-sets name] (vec ids)))

(defn create-element-set
  "Register (or overwrite) a named element set."
  [mesh name ids]
  (assoc-in mesh [:element-sets name] (vec ids)))

(defn create-face-set
  "Register (or overwrite) a named face set. `faces` is a vector of
  triangular faces, each `[a b c]` node ids — the surface a `:pressure`
  boundary condition acts on."
  [mesh name faces]
  (assoc-in mesh [:face-sets name] (mapv vec faces)))

;; ---------------------------------------------------------------------------
;; element constructors
;; ---------------------------------------------------------------------------

(defn beam2 "2-node beam / bar." [id nodes] {:type :beam2 :id id :nodes (vec nodes)})
(defn tri3 "3-node triangle (linear)." [id nodes] {:type :tri3 :id id :nodes (vec nodes)})
(defn tri6 "6-node triangle (quadratic)." [id nodes] {:type :tri6 :id id :nodes (vec nodes)})
(defn quad4 "4-node quadrilateral." [id nodes] {:type :quad4 :id id :nodes (vec nodes)})
(defn tet4 "4-node tetrahedron." [id nodes] {:type :tet4 :id id :nodes (vec nodes)})
(defn tet10 "10-node tetrahedron (quadratic)." [id nodes] {:type :tet10 :id id :nodes (vec nodes)})
(defn hex8 "8-node hexahedron." [id nodes] {:type :hex8 :id id :nodes (vec nodes)})

(defn element-id
  "Return the element id regardless of variant."
  [element]
  (:id element))

(defn mesh-stats
  "Compute basic quality statistics. Element quality is approximated as
  1.0 for all well-formed elements, matching kami-cae's placeholder (a
  real mesher would compute aspect-ratio / Jacobian metrics)."
  [mesh]
  (let [quality 1.0
        n-elems (count (:elements mesh))]
    {:node-count (count (:nodes mesh))
     :element-count n-elems
     :min-quality (if (zero? n-elems) 0.0 quality)
     :avg-quality (if (zero? n-elems) 0.0 quality)}))

(defn generate-box-mesh
  "Generate a regular hexahedral mesh of a `width` x `height` x `depth` box
  with `divisions` cells along each axis. Direct port of kami-cae's
  `mesh::generate_box_mesh` (node/element iteration order preserved so
  ids match the Rust implementation 1:1)."
  [width height depth divisions]
  (let [n (inc divisions)
        node-id (fn [iz iy ix] (+ (* iz n n) (* iy n) ix))
        with-nodes
        (reduce
         (fn [mesh [iz iy ix]]
           (let [x (* (/ (double ix) divisions) width)
                 y (* (/ (double iy) divisions) height)
                 z (* (/ (double iz) divisions) depth)]
             (:mesh (add-node mesh [x y z]))))
         (new-mesh)
         (for [iz (range n) iy (range n) ix (range n)] [iz iy ix]))
        [with-elements _eid]
        (reduce
         (fn [[mesh eid] [iz iy ix]]
           (let [base (fn [dz dy dx] (node-id (+ iz dz) (+ iy dy) (+ ix dx)))
                 nodes [(base 0 0 0) (base 0 0 1) (base 0 1 1) (base 0 1 0)
                        (base 1 0 0) (base 1 0 1) (base 1 1 1) (base 1 1 0)]]
             [(add-element mesh (hex8 eid nodes)) (inc eid)]))
         [with-nodes 0]
         (for [iz (range divisions) iy (range divisions) ix (range divisions)] [iz iy ix]))]
    with-elements))
