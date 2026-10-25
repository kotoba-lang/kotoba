(ns genesis.obb
  "Oriented-bounding-box SAT + contact manifold (stable resting).

  A single deepest-point contact (the EPA result from `genesis.convex`)
  lets a box wobble/rotate on a surface; stable stacking needs a
  multi-point contact manifold — the piece PhysX/Box2D generate by
  reference/incident-face clipping. This adds OBB-OBB SAT (15 axes) for
  the normal + min penetration, and a multi-point manifold (vertex-in-face,
  both directions).

  Honest scope: OBB-OBB (box) only — general convex manifold needs
  hull-face topology. Clean-room, CPU/WASM.

  An `Obb` is `{:center v3 :half v3 :axes [ax ay az]}` (3 orthonormal
  world-frame axes, from rotating a `rot` function over unit axes).

  Restored from kotoba-lang/kami-engine `kami-genesis/src/obb.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math)."
  (:require [genesis.vec3 :as v3]))

(defn ->obb
  "`rot` is a vec3->vec3 rotation function (default identity)."
  ([center half] (->obb center half identity))
  ([center half rot]
   {:center center :half half
    :axes [(rot v3/x-axis) (rot v3/y-axis) (rot v3/z-axis)]}))

(defn- radius [{:keys [half axes]} axis]
  (reduce + (map (fn [h a] (* h (Math/abs (v3/dot a axis)))) half axes)))

(defn corners [{:keys [center half axes]}]
  (vec (for [sx [-1.0 1.0] sy [-1.0 1.0] sz [-1.0 1.0]]
         (reduce v3/add center
                 [(v3/scale (nth axes 0) (* sx (nth half 0)))
                  (v3/scale (nth axes 1) (* sy (nth half 1)))
                  (v3/scale (nth axes 2) (* sz (nth half 2)))]))))

(defn- point-under-face
  "Signed depth of world point `p` below this box's surface along `n`
  (positive = inside), or nil if outside the box's lateral extent."
  [{:keys [center half axes]} p n]
  (let [d (v3/sub p center)]
    (loop [k 0 depth-along-n ##Inf lateral-ok? true]
      (if (>= k 3)
        (when (and lateral-ok? (not= depth-along-n ##Inf) (> depth-along-n -1e-4)) depth-along-n)
        (let [comp (v3/dot d (nth axes k))
              aligned (Math/abs (v3/dot (nth axes k) n))]
          (if (> aligned 0.9)
            (recur (inc k)
                   (- (nth half k) (* comp (Math/signum (v3/dot n (nth axes k)))))
                   lateral-ok?)
            (recur (inc k) depth-along-n
                   (and lateral-ok? (<= (Math/abs comp) (+ (nth half k) 1e-4))))))))))

(defn obb-sat
  "OBB-OBB SAT: returns `[normal-a->b penetration]` along the min-overlap
  axis, or nil if separated."
  [a b]
  (let [t (v3/sub (:center b) (:center a))
        cross-axes (for [ai (:axes a) bj (:axes b)
                          :let [c (v3/cross ai bj)]
                          :when (> (v3/length-squared c) 1e-8)]
                      (v3/normalize c))
        axes (concat (:axes a) (:axes b) cross-axes)]
    (loop [axes (seq axes) best-overlap ##Inf best-axis v3/z-axis]
      (if (nil? axes)
        (let [n (if (< (v3/dot best-axis t) 0.0) (v3/neg best-axis) best-axis)]
          [n best-overlap])
        (let [ln (v3/normalize-or-zero (first axes))]
          (if (< (v3/length-squared ln) 0.5)
            (recur (next axes) best-overlap best-axis)
            (let [dist (Math/abs (v3/dot t ln))
                  overlap (- (+ (radius a ln) (radius b ln)) dist)]
              (if (< overlap 0.0)
                nil
                (if (< overlap best-overlap)
                  (recur (next axes) overlap ln)
                  (recur (next axes) best-overlap best-axis))))))))))

(defn obb-manifold
  "OBB-OBB contact manifold (multi-point, for stable resting), or nil if
  the boxes are separated."
  [a b]
  (when-let [[n _depth] (obb-sat a b)]
    (let [pts-b (keep (fn [c] (when-let [d (point-under-face a c n)]
                                 (when (>= d -1e-4) [c d])))
                       (corners b))
          pts-a (keep (fn [c] (when-let [d (point-under-face b c (v3/neg n))]
                                 (when (>= d -1e-4) [c d])))
                      (corners a))
          points (concat pts-b pts-a)
          uniq (reduce
                 (fn [acc [p d]]
                   (if-let [idx (first (keep-indexed (fn [i [q _]] (when (< (v3/length (v3/sub q p)) 1e-3) i)) acc))]
                     (update acc idx (fn [[q dq]] (if (> d dq) [q d] [q dq])))
                     (conj acc [p d])))
                 [] points)]
      (when (seq uniq)
        {:normal n :points uniq}))))
