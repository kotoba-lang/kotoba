(ns engineer.constraint
  "2D geometric constraint solver. Restored from kami-eng-core's `constraint`
  module (kami-engine/kami-eng-core/src/lib.rs, deleted PR #82). Pure data —
  points are `[x y]` 2-vectors (glam::DVec2 in the original), constraints are
  maps, and `solve` re-evaluates constraint status without mutation.

  This is a status-evaluator, not a full Newton-Raphson relaxation solver
  (the original Rust never implemented iterative point-position solving
  either — `max-iterations`/`tolerance` existed but `solve` only classified
  constraint status against the current point positions). Kept as such for
  fidelity; a real geometric solver is future work if a domain repo needs it.")

(def kinds
  #{:coincident :parallel :perpendicular :tangent :equal :horizontal :vertical
    :fixed :symmetric :concentric :midpoint :collinear :distance :angle
    :radius :diameter})

(def statuses
  #{:satisfied :under-constrained :over-constrained :conflicting})

(defn solver
  "A fresh constraint solver: no points, no constraints."
  ([] (solver {}))
  ([opts]
   {:points []
    :constraints []
    :max-iterations (:max-iterations opts 100)
    :tolerance (:tolerance opts 1e-10)}))

(defn add-point
  "Add point `id` at position `[x y]`."
  [solver id pos]
  (update solver :points conj [id pos]))

(defn add-constraint
  "Add a constraint map `{:id :kind :entity-refs :value :status}`."
  [solver constraint]
  (update solver :constraints conj constraint))

(defn- find-point [solver id]
  (some (fn [[pid p]] (when (= pid id) p)) (:points solver)))

(defn- distance [[ax ay] [bx by]]
  (Math/sqrt (+ (* (- bx ax) (- bx ax)) (* (- by ay) (- by ay)))))

(defn- evaluate-constraint [solver {:keys [kind entity-refs value]}]
  (let [tol (:tolerance solver)]
    (case kind
      :distance
      (if (< (count entity-refs) 2)
        :conflicting
        (let [p1 (find-point solver (first entity-refs))
              p2 (find-point solver (second entity-refs))]
          (if (and p1 p2 value)
            (if (< (Math/abs (- (distance p1 p2) value)) tol)
              :satisfied :under-constrained)
            :conflicting)))

      :horizontal
      (if (< (count entity-refs) 2)
        :conflicting
        (let [p1 (find-point solver (first entity-refs))
              p2 (find-point solver (second entity-refs))]
          (if (and p1 p2)
            (if (< (Math/abs (- (second p1) (second p2))) tol)
              :satisfied :under-constrained)
            :conflicting)))

      :vertical
      (if (< (count entity-refs) 2)
        :conflicting
        (let [p1 (find-point solver (first entity-refs))
              p2 (find-point solver (second entity-refs))]
          (if (and p1 p2)
            (if (< (Math/abs (- (first p1) (first p2))) tol)
              :satisfied :under-constrained)
            :conflicting)))

      :coincident
      (if (< (count entity-refs) 2)
        :conflicting
        (let [p1 (find-point solver (first entity-refs))
              p2 (find-point solver (second entity-refs))]
          (if (and p1 p2)
            (if (< (distance p1 p2) tol)
              :satisfied :under-constrained)
            :conflicting)))

      :satisfied)))

(defn solve
  "Re-evaluate every constraint's status against current point positions.
  Returns the updated constraint vector (does not mutate `solver` — the
  caller threads the result back via `assoc :constraints`)."
  [solver]
  (mapv (fn [c] (assoc c :status (evaluate-constraint solver c)))
        (:constraints solver)))
