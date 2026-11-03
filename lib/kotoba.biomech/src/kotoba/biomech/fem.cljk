(ns kotoba.biomech.fem
  "Bone FEM via kotoba-lang/fea (Phase 2 backend).

  Bridges biomech tissue material properties into fea's linear-static
  beam2 and tet4 solvers:
  - :beam2 models slender bone as a unit-area axial bar.
  - :tet4 models 3-D linear-elastic deformation, including bending/shear;
    this namespace currently provides a reference cube mesh.
  - fea's beam2 uses a unit cross-section (A = 1 m²) and axial loading
    only (not transverse bending). Stresses therefore come back as
    Pa = N/m² (since A = 1), and the analytic reference is delta = F·L/E,
    sigma = F/A = F.
  Arbitrary anatomical mesh ingestion and hex8 elements remain future work."
  (:require [kotoba.fea.mesh :as fea-mesh]
            [kotoba.fea.solver :as fea-solver]
            [kotoba.fea.boundary :as fea-boundary]
            [kotoba.biomech.tissue :as tissue]))

(defn tissue->fea-material
  "Build a fea :linear-elastic material map from a biomech tissue.
  Uses the tissue's youngs-modulus / poissons-ratio / density. Tissues
  whose :model/:type is not :linear-elastic are still projected to
  linear-elastic using their effective youngs-modulus — a modelling
  simplification (fea Phase-1 is linear-static only)."
  [t]
  ;; REFUSE AN ANISOTROPIC POISSON'S RATIO RATHER THAN SOLVING WITH IT.
  ;; fea's :linear-elastic material is isotropic, and isotropy requires
  ;; -1 < nu < 1/2. A tissue measured anisotropically may exceed that bound
  ;; legitimately (the anulus fibrosus does, at nu21 = 0.67), and passing it
  ;; through produces a NEGATIVE bulk modulus, K = E/(3(1-2nu)) with
  ;; 1-2nu < 0. Nothing downstream raises: the solve returns finite numbers
  ;; that mean nothing. Every tissue in the shipped presets that HAS a
  ;; Poisson's ratio below 1/2 is unaffected; nil still takes the historical
  ;; 0.3 default, because changing that would alter existing behaviour for
  ;; tissues this guard has nothing to say about.
  (let [nu (tissue/poissons-ratio t)]
    (when (and (some? nu) (not (tissue/isotropically-admissible? t)))
      (throw (ex-info
              (str "tissue " (pr-str (:name t)) " has Poisson's ratio " nu
                   ", outside the isotropic range -1 < nu < 1/2; fea's"
                   " linear-elastic material is isotropic and would compute a"
                   " negative bulk modulus. Use an anisotropic path or an"
                   " explicitly chosen isotropic surrogate.")
              {:type :anisotropic-tissue-in-isotropic-solver
               :tissue (:name t)
               :poissons-ratio nu}))))
  {:name (str (or (:name t) "tissue"))
   :model {:type :linear-elastic
           :youngs-modulus (double (or (tissue/youngs-modulus t) 1.0e6))
           :poissons-ratio (double (or (tissue/poissons-ratio t) 0.3))
           :density (double (or (tissue/density t) 1000.0))}})

(defn axial-bar-mesh
  "Build a 1-D beam2 mesh along +X from x=0 to x=length, `divisions`
  beam2 elements. Node-set \"fixed\" = root node (id 0); \"tip\" = last
  node. Returns a fea mesh map."
  [length divisions]
  (let [n (max 1 (int divisions))
        dx (/ (double length) n)
        {:keys [mesh ids]}
        (loop [i 0 m (fea-mesh/new-mesh) ids []]
          (if (> i n)
            {:mesh m :ids ids}
            (let [x (* dx i)
                  {:keys [mesh id]} (fea-mesh/add-node m [(double x) 0.0 0.0])]
              (recur (inc i) mesh (conj ids id)))))
        mesh-with-elems
        (loop [j 0 m mesh]
          (if (>= j n)
            m
            (let [e (fea-mesh/beam2 j [(nth ids j) (nth ids (inc j))])]
              (recur (inc j) (fea-mesh/add-element m e)))))]
    (-> mesh-with-elems
        (fea-mesh/create-node-set "fixed" [(first ids)])
        (fea-mesh/create-node-set "tip" [(peek ids)]))))

(defn solve-axial-bar
  "Solve a 1-D axial bar of tissue `t`, length L [m], `divisions` beam2
  elements, under axial tip load F [N] along +X (positive = tension).
  Root node is fully fixed. Returns fea's result map
  (:max-displacement, :max-stress, :displacement, :stress, ...).

  Analytic reference (fea A = 1 m²): delta = F·L / E, sigma = F / A = F."
  [t length force divisions]
  (let [mesh (axial-bar-mesh length divisions)
        mat  (tissue->fea-material t)
        bcs  [(fea-boundary/displacement "fixed" fea-boundary/dof-all [0.0 0.0 0.0])
              (fea-boundary/force "tip" [(double force) 0.0 0.0])]]
    (fea-solver/solve-linear-static mesh mat bcs)))

;; --- 3-D tet4 path (fea Phase-2: tet4 element assembly) ---

(defn tet4-cube-mesh
  "Cube [0,L]^3 split into 5 tet4 elements (the standard split along the
  0-6 body diagonal). Node-set \"fixed\" = bottom face (z=0, nodes 0-3);
  \"load\" = top face (z=L, nodes 4-7). Returns a fea mesh map."
  [L]
  (let [coords [[0.0 0.0 0.0] [L 0.0 0.0] [L L 0.0] [0.0 L 0.0]
                [0.0 0.0 L] [L 0.0 L] [L L L] [0.0 L L]]
        {:keys [mesh ids]}
        (loop [i 0 m (fea-mesh/new-mesh) ids []]
          (if (= i 8)
            {:mesh m :ids ids}
            (let [{:keys [mesh id]} (fea-mesh/add-node m (coords i))]
              (recur (inc i) mesh (conj ids id)))))]
    (-> mesh
        (fea-mesh/add-element (fea-mesh/tet4 0 [(ids 0) (ids 1) (ids 2) (ids 6)]))
        (fea-mesh/add-element (fea-mesh/tet4 1 [(ids 0) (ids 2) (ids 3) (ids 6)]))
        (fea-mesh/add-element (fea-mesh/tet4 2 [(ids 0) (ids 3) (ids 7) (ids 6)]))
        (fea-mesh/add-element (fea-mesh/tet4 3 [(ids 0) (ids 7) (ids 4) (ids 6)]))
        (fea-mesh/add-element (fea-mesh/tet4 4 [(ids 0) (ids 4) (ids 5) (ids 6)]))
        (fea-mesh/create-node-set "fixed" [(ids 0) (ids 1) (ids 2) (ids 3)])
        (fea-mesh/create-node-set "load"   [(ids 4) (ids 5) (ids 6) (ids 7)]))))

(defn solve-tet4-cube
  "3-D cube of tissue `t`, side L [m], under axial tip load F [N] along +Z
  (positive = tension). Bottom face (z=0) fixed. Returns fea's result map.
  Uses fea's tet4 element assembly (3-D elasticity — bending / shear, not
  just axial), the Phase-2 expansion of fea's solver."
  [t L force]
  (let [mesh (tet4-cube-mesh (double L))
        mat  (tissue->fea-material t)
        bcs  [(fea-boundary/displacement "fixed" fea-boundary/dof-all [0.0 0.0 0.0])
              (fea-boundary/force "load" [0.0 0.0 (double force)])]]
    (fea-solver/solve-linear-static mesh mat bcs)))
