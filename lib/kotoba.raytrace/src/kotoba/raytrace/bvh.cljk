(ns kotoba.raytrace.bvh
  "Linear BVH (LBVH) — CPU acceleration-structure build + reference traversal.
   1:1 port of kami-rt's `bvh.rs`. Triangle centroids are ranked by 30-bit
   Morton code (Z-order), sorted, and split at the median to build a binary
   BVH whose node array is flat and GPU-uploadable (kotoba.raytrace.gpu
   consumes the same layout — the WGSL ray-query / LBVH-compute path would
   consume the same `nodes` layout on the GPU side). This traversal is the
   reference oracle that pins the structure's correctness without a GPU.

   Pure CPU math throughout — no GPU calls anywhere in this namespace (there
   were none in bvh.rs either; that's the whole point of the crate split)."
  (:require [kotoba.raytrace.vec3 :as vec3]
            [kotoba.raytrace.mathx :as mathx]
            [kotoba.raytrace.config :as config]))

;; ---------------------------------------------------------------------------
;; Aabb — axis-aligned bounding box. `{:min Vec3 :max Vec3}`.

(defn aabb-empty []
  {:min (vec3/splat #?(:clj Double/POSITIVE_INFINITY :cljs js/Infinity))
   :max (vec3/splat #?(:clj Double/NEGATIVE_INFINITY :cljs (- js/Infinity)))})

(defn aabb-grow-point [aabb p]
  {:min (vec3/vmin (:min aabb) p)
   :max (vec3/vmax (:max aabb) p)})

(defn aabb-union [a b]
  {:min (vec3/vmin (:min a) (:min b))
   :max (vec3/vmax (:max a) (:max b))})

(defn aabb-centroid [{bmin :min bmax :max}]
  (vec3/scale (vec3/add bmin bmax) 0.5))

(defn aabb-hit?
  "Slab test: does the ray (`origin`/`inv-dir`, inv-dir = componentwise 1/dir)
   hit `aabb` within [t0,t1]?"
  [{bmin :min bmax :max} origin inv-dir t0 t1]
  (loop [a 0 tmin t0 tmax t1]
    (if (= a 3)
      true
      (let [inv (inv-dir a)
            ta0 (* (- (bmin a) (origin a)) inv)
            tb0 (* (- (bmax a) (origin a)) inv)
            [ta tb] (if (< inv 0.0) [tb0 ta0] [ta0 tb0])
            tmin' (max tmin ta)
            tmax' (min tmax tb)]
        (if (< tmax' tmin')
          false
          (recur (inc a) tmin' tmax'))))))

;; ---------------------------------------------------------------------------
;; Tri — a triangle (CCW). `{:v0 Vec3 :v1 Vec3 :v2 Vec3 :id int}`.

(defn tri-aabb [{:keys [v0 v1 v2]}]
  (-> (aabb-empty)
      (aabb-grow-point v0)
      (aabb-grow-point v1)
      (aabb-grow-point v2)))

(defn tri-centroid [{:keys [v0 v1 v2]}]
  (vec3/scale (vec3/add v0 (vec3/add v1 v2)) (/ 1.0 3.0)))

(defn tri-intersect
  "Moller-Trumbore ray<->triangle; returns the front-face distance `t` if hit,
   else nil."
  [{:keys [v0 v1 v2]} origin dir]
  (let [{:bvh/keys [det-epsilon hit-t-epsilon]} config/config
        e1 (vec3/sub v1 v0)
        e2 (vec3/sub v2 v0)
        p (vec3/cross dir e2)
        det (vec3/dot e1 p)]
    (when (>= (mathx/abs det) det-epsilon)
      (let [inv (/ 1.0 det)
            tvec (vec3/sub origin v0)
            u (* (vec3/dot tvec p) inv)]
        (when (<= 0.0 u 1.0)
          (let [q (vec3/cross tvec e1)
                v (* (vec3/dot dir q) inv)]
            (when-not (or (< v 0.0) (> (+ u v) 1.0))
              (let [t (* (vec3/dot e2 q) inv)]
                (when (> t hit-t-epsilon) t)))))))))

;; ---------------------------------------------------------------------------
;; Node — flat BVH node. Leaf when `count > 0` (refs [start,start+count) in
;; tri-order); internal otherwise (`left`/`right` index into `nodes`).

(defn- expand-bits
  "Expand a 10-bit integer into 30 bits, inserting two 0s before each bit."
  [v]
  (let [v (bit-and v 0x3ff)
        v (bit-and (bit-or v (bit-shift-left v 16)) 0x030000ff)
        v (bit-and (bit-or v (bit-shift-left v 8)) 0x0300f00f)
        v (bit-and (bit-or v (bit-shift-left v 4)) 0x030c30c3)
        v (bit-and (bit-or v (bit-shift-left v 2)) 0x09249249)]
    v))

(defn morton3
  "30-bit Morton code for a point in the unit cube [0,1]^3."
  [p]
  (let [scale (:bvh/morton-scale config/config)
        q (fn [c] (mathx/trunc (mathx/round (* (mathx/clamp c 0.0 1.0) scale))))]
    (bit-or (bit-shift-left (expand-bits (q (vec3/x p))) 2)
            (bit-shift-left (expand-bits (q (vec3/y p))) 1)
            (expand-bits (q (vec3/z p))))))

;; ---------------------------------------------------------------------------
;; Bvh — a built BVH: a flat node array (root at 0) + the Morton-sorted
;; triangle order. `{:nodes [Node...] :tri-order [int...] :tris [Tri...]}`.

(defn- build-range!
  "Recursively build nodes for tri-order[lo,hi); returns the node index.
   `nodes` is an atom holding the (parent-before-children) node vector, the
   same push-then-recurse order bvh.rs uses with `&mut Vec<Node>`."
  [tris order lo hi nodes]
  (let [leaf-max (:bvh/leaf-max config/config)
        bb (reduce (fn [acc i] (aabb-union acc (tri-aabb (nth tris i))))
                    (aabb-empty)
                    (subvec order lo hi))
        idx (count @nodes)]
    (swap! nodes conj {:aabb bb :left 0 :right 0 :start lo :count 0})
    (let [cnt (- hi lo)]
      (if (<= cnt leaf-max)
        (do (swap! nodes assoc-in [idx :count] cnt)
            idx)
        (let [mid (+ lo (quot cnt 2)) ; median in Morton order
              left (build-range! tris order lo mid nodes)
              right (build-range! tris order mid hi nodes)]
          (swap! nodes update idx merge {:left left :right right})
          idx)))))

(defn build
  "Build an LBVH over `tris` (a vector of Tri maps). Empty input yields a
   single empty leaf."
  [tris]
  (if (empty? tris)
    {:nodes [{:aabb (aabb-empty) :left 0 :right 0 :start 0 :count 0}]
     :tri-order []
     :tris tris}
    (let [extent-eps (:bvh/extent-epsilon config/config)
          cbounds (reduce (fn [acc t] (aabb-grow-point acc (tri-centroid t)))
                           (aabb-empty) tris)
          extent (vec3/vmax (vec3/sub (:max cbounds) (:min cbounds))
                             (vec3/splat extent-eps))
          keyed (->> tris
                     (map-indexed
                      (fn [i t]
                        (let [n (vec3/div (vec3/sub (tri-centroid t) (:min cbounds)) extent)]
                          [(morton3 n) i])))
                     (sort-by first))
          tri-order (mapv second keyed)
          nodes (atom [])]
      (build-range! tris tri-order 0 (count tri-order) nodes)
      {:nodes @nodes :tri-order tri-order :tris tris})))

(defn node-count
  "Total node count (1 for an empty BVH)."
  [bvh]
  (count (:nodes bvh)))

(defn traverse
  "Nearest front-face hit of the ray against the BVH, or nil. A hit is
   `{:t float :tri-id int}`."
  [{:keys [nodes tri-order tris]} origin dir]
  (when (seq tri-order)
    (let [inv-dir (vec3/recip dir)]
      (loop [stack [0] best nil]
        (if (empty? stack)
          best
          (let [ni (peek stack)
                stack (pop stack)
                node (nth nodes ni)
                tmax (if best (:t best) #?(:clj Double/POSITIVE_INFINITY :cljs js/Infinity))]
            (if-not (aabb-hit? (:aabb node) origin inv-dir 0.0 tmax)
              (recur stack best)
              (if (pos? (:count node))
                (recur stack
                       (reduce
                        (fn [b k]
                          (let [tri (nth tris (nth tri-order k))
                                t (tri-intersect tri origin dir)]
                            (if (and t (or (nil? b) (< t (:t b))))
                              {:t t :tri-id (:id tri)}
                              b)))
                        best
                        (range (:start node) (+ (:start node) (:count node)))))
                (recur (conj stack (:left node) (:right node)) best)))))))))
