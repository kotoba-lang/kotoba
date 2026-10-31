(ns vehicle.triangle
  "Triangle -- aero / collision surface formed by three nodes.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   BeamNG uses triangles for two purposes: aerodynamic drag/lift, and as
   the collision hull surface. This port only carries the data shape (aero
   coefficients, node references, render group) -- the original Rust module
   has no additional logic beyond construction, matching this port exactly."
  )

;; group: :body | :wing | :underbody | :window

(defn new-triangle [id n1 n2 n3]
  {:id id :n1 n1 :n2 n2 :n3 n3
   :drag-coef 0.30 :lift-coef 0.0 :group :body})

(defn with-aero [tri drag lift] (assoc tri :drag-coef drag :lift-coef lift))
(defn with-group [tri g] (assoc tri :group g))
