(ns vehicle.rigid-chassis
  "Rigid chassis projection (shape-matching constraint).
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   After XPBD has settled the soft-body beam network, the chassis body
   nodes (:body / :cargo groups, NOT :wheel-hub / :wheel-tire) are projected
   onto a best-fit rigid transform (translation-only, per the original
   `project`) of their initial rest configuration."
  (:require [vehicle.vec3 :as v3]
            [vehicle.node :as node]))

(defn build-from
  "Build a rigid-chassis descriptor from current node positions (a seq of
   node maps)."
  [nodes]
  (let [members-info
        (->> nodes
             (filter (fn [n] (contains? #{:body :cargo} (:group n))))
             (remove node/fixed?))
        members (mapv :id members-info)
        positions (mapv :position members-info)
        mass (mapv :mass members-info)
        total-mass (reduce + 0.0 mass)
        com (if (> total-mass 0.0)
              (v3/scale (reduce v3/add v3/zero
                                 (map (fn [p m] (v3/scale p m)) positions mass))
                         (/ 1.0 total-mass))
              v3/zero)
        rest-relative (mapv (fn [p] (v3/sub p com)) positions)]
    {:members members
     :rest-relative rest-relative
     :mass mass
     :total-mass total-mass
     :enabled true}))

(defn- index-by-id [nodes]
  (into {} (map-indexed (fn [i n] [(:id n) i]) nodes)))

(def blend 0.30)

(defn project
  "Project body / cargo nodes onto the rigid transform. `nodes` is a vector
   of node maps; returns the updated vector."
  [rigid nodes _dt]
  (if (or (not (:enabled rigid)) (<= (:total-mass rigid) 0.0) (empty? (:members rigid)))
    nodes
    (let [idx (index-by-id nodes)
          members (:members rigid)
          mass (:mass rigid)
          total-mass (:total-mass rigid)
          member-idxs (mapv (fn [id] (get idx id)) members)
          com (v3/scale
               (reduce v3/add v3/zero
                       (map (fn [i m] (if i (v3/scale (:position (nth nodes i)) m) v3/zero))
                            member-idxs mass))
               (/ 1.0 total-mass))
          com-vel (v3/scale
                   (reduce v3/add v3/zero
                           (map (fn [i m] (if i (v3/scale (:velocity (nth nodes i)) m) v3/zero))
                                member-idxs mass))
                   (/ 1.0 total-mass))
          r v3/mat3-identity]
      (reduce
       (fn [nodes* [i rest-rel]]
         (if (nil? i)
           nodes*
           (let [r-xi (v3/mat3-mul-vec3 r rest-rel)
                 target-pos (v3/add com r-xi)]
             (update nodes* i
                     (fn [n]
                       (-> n
                           (assoc :position (v3/lerp (:position n) target-pos blend))
                           (assoc :velocity (v3/lerp (:velocity n) com-vel blend))))))))
       nodes
       (map vector member-idxs (:rest-relative rigid))))))

;; ---- Shape-matching internals (ported for test parity) ----

(defn outer-product [a b]
  (v3/mat3-from-cols
   (v3/v3 (* (:x a) (:x b)) (* (:y a) (:x b)) (* (:z a) (:x b)))
   (v3/v3 (* (:x a) (:y b)) (* (:y a) (:y b)) (* (:z a) (:y b)))
   (v3/v3 (* (:x a) (:z b)) (* (:y a) (:z b)) (* (:z a) (:z b)))))

(declare finish-det)

(defn polar-rotation
  "Polar decomposition of a non-singular 3x3 matrix A = R.S where R is an
   orthogonal rotation. Uses Higham's iteration."
  [a]
  (if (< (Math/abs (v3/mat3-determinant a)) 1e-9)
    v3/mat3-identity
    (loop [r a iter 0]
      (if (>= iter 6)
        (finish-det r)
        (let [inv (v3/mat3-inverse r)]
          (if (or (nil? inv) (not (v3/mat3-finite? inv)))
            (finish-det r)
            (let [r-inv-t (v3/mat3-transpose inv)
                  next (v3/mat3-scale (v3/mat3-add r r-inv-t) 0.5)
                  diff (v3/mat3-abs-diff (v3/mat3-sub next r))]
              (if (< diff 1e-7)
                (finish-det next)
                (recur next (inc iter))))))))))

(defn- finish-det [r]
  (if (< (v3/mat3-determinant r) 0.0)
    (v3/mat3-from-cols (:c0 r) (:c1 r) (v3/neg (:c2 r)))
    r))
