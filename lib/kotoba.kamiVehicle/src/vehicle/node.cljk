(ns vehicle.node
  "Mass-point node -- atomic unit of the BeamNG-style soft body.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   Every vehicle is a cloud of nodes connected by beams. A node carries
   position, velocity, accumulated force, mass, and a few per-node material
   coefficients (drag, ground friction). Plastic deformation lives on the
   beam; the node only integrates Newton's 2nd law."
  (:require [vehicle.vec3 :as v3]))

;; NodeGroup enum -> keyword: :body | :wheel-hub | :wheel-tire | :cargo | :anchor

(defn new-node
  "Construct a node. `position` is a vec3 map."
  ([id position mass] (new-node id position mass :body))
  ([id position mass group]
   (let [mass (double mass)
         inv-mass (if (> mass 0.0) (/ 1.0 mass) 0.0)]
     {:id id
      :position position
      :velocity v3/zero
      :force v3/zero
      :mass mass
      :inv-mass inv-mass
      :drag 0.4
      :friction 1.0
      :restitution 0.05
      :group group})))

(defn anchor [id position]
  (assoc (new-node id position 0.0) :group :anchor))

(defn with-group [node group] (assoc node :group group))
(defn with-drag [node drag] (assoc node :drag drag))
(defn with-friction [node friction] (assoc node :friction friction))

(defn fixed? [node] (<= (:mass node) 0.0))

(defn refresh-inv-mass [node]
  (assoc node :inv-mass (if (> (:mass node) 0.0) (/ 1.0 (:mass node)) 0.0)))
