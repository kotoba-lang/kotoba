(ns kami.modeling.csg)

(def ^:private epsilon 1.0e-5)
(def ^:private coplanar 0)
(def ^:private front 1)
(def ^:private back 2)
(def ^:private spanning 3)

(defn- v+ [a b] (mapv + a b))
(defn- v- [a b] (mapv - a b))
(defn- v* [a s] (mapv #(* % s) a))
(defn- dot [a b] (reduce + (map * a b)))
(defn- cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn- length [v] (#?(:clj Math/sqrt :cljs js/Math.sqrt) (dot v v)))
(defn- normalize [v] (let [m (length v)] (when (< m epsilon) (throw (ex-info "degenerate CSG polygon" {}))) (v* v (/ 1.0 m))))
(defn- lerp [a b t] (v+ a (v* (v- b a) t)))

(defn- polygon [vertices]
  (let [[a b c] vertices normal (normalize (cross (v- b a) (v- c a)))]
    {:vertices (vec vertices) :plane {:normal normal :w (dot normal a)}}))
(defn- flip-polygon [{:keys [vertices plane]}]
  {:vertices (vec (reverse vertices)) :plane {:normal (v* (:normal plane) -1) :w (- (:w plane))}})

(defn- split-polygon [plane poly]
  (let [{:keys [normal w]} plane vertices (:vertices poly)
        types (mapv (fn [v] (let [t (- (dot normal v) w)] (cond (< t (- epsilon)) back (> t epsilon) front :else coplanar))) vertices)
        kind (reduce bit-or types)]
    (case kind
      0 (if (pos? (dot normal (get-in poly [:plane :normal]))) {:coplanar-front [poly]} {:coplanar-back [poly]})
      1 {:front [poly]}
      2 {:back [poly]}
      3 (let [n (count vertices)
              [f b] (reduce (fn [[f b] i]
                              (let [j (mod (inc i) n) vi (nth vertices i) vj (nth vertices j)
                                    ti (nth types i) tj (nth types j)
                                    f (if (not= ti back) (conj f vi) f)
                                    b (if (not= ti front) (conj b vi) b)]
                                (if (= spanning (bit-or ti tj))
                                  (let [t (/ (- w (dot normal vi)) (dot normal (v- vj vi))) v (lerp vi vj t)]
                                    [(conj f v) (conj b v)]) [f b]))) [[] []] (range n))]
          (cond-> {} (>= (count f) 3) (assoc :front [(polygon f)]) (>= (count b) 3) (assoc :back [(polygon b)]))))))

(declare build-node clip-polygons)
(defn- node
  ([] {:plane nil :front nil :back nil :polygons []})
  ([polygons] (build-node (node) polygons)))

(defn- build-node [tree polygons]
  (if (empty? polygons) tree
      (let [plane (or (:plane tree) (:plane (first polygons)))
            split (reduce (fn [result p]
                            (let [parts (split-polygon plane p)]
                              (-> result
                                  (update :polygons into (concat (:coplanar-front parts) (:coplanar-back parts)))
                                  (update :front into (:front parts))
                                  (update :back into (:back parts)))))
                          {:polygons (:polygons tree) :front [] :back []} polygons)]
        {:plane plane :polygons (:polygons split)
         :front (if (seq (:front split)) (build-node (or (:front tree) (node)) (:front split)) (:front tree))
         :back (if (seq (:back split)) (build-node (or (:back tree) (node)) (:back split)) (:back tree))})))

(defn- all-polygons [tree]
  (vec (concat (:polygons tree) (when (:front tree) (all-polygons (:front tree)))
               (when (:back tree) (all-polygons (:back tree))))))
(defn- invert-node [tree]
  {:plane (when-let [p (:plane tree)] {:normal (v* (:normal p) -1) :w (- (:w p))})
   :polygons (mapv flip-polygon (:polygons tree))
   :front (when (:back tree) (invert-node (:back tree)))
   :back (when (:front tree) (invert-node (:front tree)))})

(defn- clip-polygons [tree polygons]
  (if-not (:plane tree) polygons
    (let [split (reduce (fn [result p]
                          (let [parts (split-polygon (:plane tree) p)]
                            (-> result
                                (update :front into (concat (:coplanar-front parts) (:front parts)))
                                (update :back into (concat (:coplanar-back parts) (:back parts))))))
                        {:front [] :back []} polygons)
          front-polys (if (:front tree) (clip-polygons (:front tree) (:front split)) (:front split))
          back-polys (if (:back tree) (clip-polygons (:back tree) (:back split)) [])]
      (vec (concat front-polys back-polys)))))
(defn- clip-to [tree other]
  (assoc tree :polygons (clip-polygons other (:polygons tree))
         :front (when (:front tree) (clip-to (:front tree) other))
         :back (when (:back tree) (clip-to (:back tree) other))))

(defn- mesh-polygons [{:mesh/keys [vertices faces]}]
  (mapv #(polygon (mapv vertices %)) faces))
(defn- polygons-mesh [polygons]
  (let [verts (vec (mapcat :vertices polygons))
        counts (mapv #(count (:vertices %)) polygons)
        starts (butlast (reductions + 0 counts))]
    {:mesh/vertices verts :mesh/faces (mapv (fn [start n] (vec (range start (+ start n)))) starts counts)}))

(defn boolean-mesh [a b operation]
  (let [a0 (node (mesh-polygons a)) b0 (node (mesh-polygons b))
        result (case operation
                 :union (let [a1 (clip-to a0 b0) b1 (clip-to b0 a1)
                              b2 (invert-node b1) b3 (clip-to b2 a1) b4 (invert-node b3)]
                          (build-node a1 (all-polygons b4)))
                 :difference (let [a1 (invert-node a0) a2 (clip-to a1 b0) b1 (clip-to b0 a2)
                                   b2 (invert-node b1) b3 (clip-to b2 a2) b4 (invert-node b3)]
                               (invert-node (build-node a2 (all-polygons b4))))
                 :intersection (let [a1 (invert-node a0) b1 (clip-to b0 a1) b2 (invert-node b1)
                                     a2 (clip-to a1 b2) b3 (clip-to b2 a2) merged (build-node a2 (all-polygons b3))]
                                 (invert-node merged))
                 (throw (ex-info "unknown CSG operation" {:operation operation})))]
    (polygons-mesh (all-polygons result))))
