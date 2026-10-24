(ns kami.sculpt "Portable signed-distance-field sculpting operations.")
(defn sphere [center radius] {:sdf/kind :sphere :sdf/center center :sdf/radius radius})
(defn brush [center radius strength mode] {:brush/center center :brush/radius radius :brush/strength strength :brush/mode mode})
(defn apply-brush
  "Append a deterministic non-destructive brush operation. A mesher consumes this
  EDN stack to remesh; UI never mutates a binary mesh directly."
  [shape b] (update shape :sdf/operations (fnil conj []) b))
(defn mirrored [b axis]
  (let [[x y z] (:brush/center b) p {:x [(- x) y z] :y [x (- y) z] :z [x y (- z)]}]
    (assoc b :brush/center (get p axis))))

(defn- sin [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))
(defn- cos [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))
(defn- sqrt [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(def pi #?(:clj Math/PI :cljs js/Math.PI))
(defn- sub [a b] (mapv - a b))
(defn- add [a b] (mapv + a b))
(defn- scale [v s] (mapv #(* % s) v))
(defn- mix [a b t] (add a (scale (sub b a) t)))
(defn- length [v] (sqrt (reduce + (map #(* % %) v))))
(defn- normalize [v] (let [l (max 1.0e-9 (length v))] (scale v (/ 1 l))))

(defn sphere-mesh
  "Generate a UV sphere suitable for deterministic brush deformation."
  ([radius] (sphere-mesh radius 32 20))
  ([radius slices stacks]
   (let [positions (vec (for [j (range (inc stacks)) i (range (inc slices))
                              :let [v (/ j stacks) u (/ i slices)
                                    phi (* pi v) theta (* 2 pi u)]]
                          [(* radius (sin phi) (cos theta))
                           (* radius (cos phi))
                           (* radius (sin phi) (sin theta))]))
         cols (inc slices)
         indices (vec (mapcat (fn [[j i]]
                                (let [a (+ (* j cols) i) b (inc a) c (+ a cols) d (inc c)]
                                  [a c b b c d]))
                              (for [j (range stacks) i (range slices)] [j i])))]
     {:positions positions :normals (mapv normalize positions) :indices indices
      :masks (vec (repeat (count positions) 0.0))})))

(defn clear-mask [mesh] (assoc mesh :masks (vec (repeat (count (:positions mesh)) 0.0))))
(defn invert-mask [mesh] (update mesh :masks #(mapv (fn [v] (- 1.0 v)) (or % (repeat (count (:positions mesh)) 0.0)))))
(defn vertex-neighbours [mesh]
  (let [result (atom (vec (repeat (count (:positions mesh)) #{})))]
    (doseq [[a b c] (partition 3 (:indices mesh)) [x y] [[a b] [b c] [c a]]]
      (swap! result update x conj y) (swap! result update y conj x))
    @result))
(defn filter-mask [mesh operation]
  (let [masks (vec (or (:masks mesh) (repeat (count (:positions mesh)) 0.0))) neighbours (vertex-neighbours mesh)
        average (fn [i] (/ (reduce + (nth masks i) (map masks (nth neighbours i))) (inc (count (nth neighbours i)))))
        clamp #(max 0.0 (min 1.0 %))
        filtered (mapv (fn [i current]
                         (case operation
                           :blur (average i)
                           :sharpen (clamp (+ current (- current (average i))))
                           :grow (reduce max current (map masks (nth neighbours i)))
                           :shrink (reduce min current (map masks (nth neighbours i)))
                           (throw (ex-info "unknown mask filter" {:operation operation}))))
                       (range (count masks)) masks)]
    (assoc mesh :masks filtered)))

(defn apply-mask-brush
  "Paint or erase a per-vertex mask using the same quadratic brush falloff."
  [mesh {:brush/keys [center radius strength mode]}]
  (let [masks (or (:masks mesh) (vec (repeat (count (:positions mesh)) 0.0)))
        paint (fn [p current]
                (let [d (length (sub p center))]
                  (if (>= d radius) current
                    (let [x (- 1 (/ d radius)) amount (* strength x x)
                          value (if (= mode :mask-erase) (- current amount) (+ current amount))]
                      (max 0.0 (min 1.0 value))))))]
    (assoc mesh :masks (mapv paint (:positions mesh) masks))))

(defn apply-mesh-brush
  "Apply an actual brush displacement to mesh positions. Supported modes are
  :inflate, :smooth and :pinch. Returns a new immutable mesh."
  [mesh {:brush/keys [center radius strength mode] :as b}]
  (if (#{:mask :mask-erase} mode)
    (apply-mask-brush mesh b)
  (let [avg-radius (/ (reduce + (map length (:positions mesh))) (count (:positions mesh)))
        masks (or (:masks mesh) (repeat (count (:positions mesh)) 0.0))
        deform (fn [p n mask]
                 (let [delta (sub p center) d (length delta)]
                   (if (>= d radius) p
                     (let [falloff (let [x (- 1 (/ d radius))] (* x x))
                           amount (* strength falloff (- 1 mask))]
                       (case mode
                         :smooth (add p (scale (sub (scale (normalize p) avg-radius) p) amount))
                         :pinch (add p (scale (sub center p) (* amount 0.25)))
                         (add p (scale n amount)))))))]
    (let [positions (mapv deform (:positions mesh) (:normals mesh) masks)]
      (assoc mesh :positions positions :normals (mapv normalize positions))))))

(defn symmetry-brushes
  "Return unique brush instances for any combination of enabled symmetry axes."
  [b axes]
  (let [axes (cond (nil? axes) [] (keyword? axes) [axes] :else axes)]
    (reduce (fn [brushes axis]
              (vec (distinct (concat brushes (map #(mirrored % axis) brushes))))) [b] axes)))

(defn apply-stroke
  "Apply a brush and optional axis symmetry as one deterministic stroke."
  [mesh b symmetry-axis]
  (reduce apply-mesh-brush mesh (symmetry-brushes b symmetry-axis)))

(defn resample-stroke
  "Resample pointer input at stable world-space spacing for device-independent strokes."
  [points spacing]
  (when-not (pos? spacing) (throw (ex-info "stroke spacing must be positive" {:spacing spacing})))
  (if (< (count points) 2) (vec points)
    (loop [result [(first points)] remaining (rest points) cursor (first points)]
      (if-let [target (first remaining)]
        (let [delta (sub target cursor) d (length delta)]
          (if (>= d spacing)
            (let [next-point (add cursor (scale delta (/ spacing d)))]
              (recur (conj result next-point) remaining next-point))
            (recur result (rest remaining) target)))
        (cond-> result (> (length (sub (peek result) (last points))) 1.0e-9) (conj (last points)))))))

(defn subdivide-mesh
  "Uniformly subdivide indexed triangles while sharing edge midpoints. This is
  the deterministic topology step used by dynamic-topology and multires tools."
  [mesh]
  (let [positions (atom (vec (:positions mesh)))
        masks (atom (vec (or (:masks mesh) (repeat (count @positions) 0.0))))
        edge-cache (atom {})
        midpoint (fn [a b]
                   (let [edge (if (< a b) [a b] [b a])]
                     (if-let [i (get @edge-cache edge)] i
                       (let [i (count @positions)]
                         (swap! positions conj (mix (nth @positions a) (nth @positions b) 0.5))
                         (swap! masks conj (/ (+ (nth @masks a) (nth @masks b)) 2))
                         (swap! edge-cache assoc edge i) i))))
        triangles (partition 3 (:indices mesh))
        indices (vec (mapcat (fn [[a b c]]
                               (let [ab (midpoint a b) bc (midpoint b c) ca (midpoint c a)]
                                 [a ab ca, ab b bc, ca bc c, ab bc ca])) triangles))]
    (assoc mesh :positions @positions :normals (mapv normalize @positions) :masks @masks :indices indices)))

;; Non-destructive sculpt layers. Each layer stores additive position deltas
;; against a stable base topology; evaluation is deterministic and portable.
(defn sculpt-layer
  ([id name vertex-count] (sculpt-layer id name vertex-count {}))
  ([id name vertex-count {:keys [opacity visible?] :or {opacity 1.0 visible? true}}]
   {:sculpt.layer/id id :sculpt.layer/name name :sculpt.layer/opacity opacity
    :sculpt.layer/visible? visible? :sculpt.layer/deltas (vec (repeat vertex-count [0.0 0.0 0.0]))}))
(defn sculpt-document [base-mesh]
  (let [layer (sculpt-layer 1 "Base detail" (count (:positions base-mesh)))]
    {:sculpt/base base-mesh :sculpt/layers [layer] :sculpt/active-layer 1 :sculpt/next-layer-id 2}))
(defn find-layer [doc id] (first (filter #(= id (:sculpt.layer/id %)) (:sculpt/layers doc))))
(defn evaluate-document [doc]
  (let [base (:sculpt/base doc)
        deltas (filter :sculpt.layer/visible? (:sculpt/layers doc))
        positions (mapv (fn [index p]
                          (reduce (fn [result layer]
                                    (add result (scale (nth (:sculpt.layer/deltas layer) index)
                                                       (:sculpt.layer/opacity layer)))) p deltas))
                        (range) (:positions base))]
    (assoc base :positions positions :normals (mapv normalize positions))))
(defn add-layer [doc name]
  (let [id (:sculpt/next-layer-id doc) layer (sculpt-layer id name (count (get-in doc [:sculpt/base :positions])))]
    (-> doc (update :sculpt/layers conj layer) (assoc :sculpt/active-layer id) (update :sculpt/next-layer-id inc))))
(defn update-layer [doc id f & args]
  (update doc :sculpt/layers #(mapv (fn [layer] (if (= id (:sculpt.layer/id layer)) (apply f layer args) layer)) %)))
(defn delete-layer [doc id]
  (when (= 1 (count (:sculpt/layers doc))) (throw (ex-info "sculpt document needs one layer" {})))
  (let [layers (vec (remove #(= id (:sculpt.layer/id %)) (:sculpt/layers doc)))]
    (assoc doc :sculpt/layers layers :sculpt/active-layer
           (if (= id (:sculpt/active-layer doc)) (:sculpt.layer/id (first layers)) (:sculpt/active-layer doc)))))
(defn move-layer [doc id target-index]
  (let [layers (:sculpt/layers doc) source-index (first (keep-indexed #(when (= id (:sculpt.layer/id %2)) %1) layers))]
    (when-not source-index (throw (ex-info "sculpt layer not found" {:id id})))
    (let [target (max 0 (min (dec (count layers)) target-index)) layer (nth layers source-index)
          without (vec (concat (subvec layers 0 source-index) (subvec layers (inc source-index))))
          reordered (vec (concat (subvec without 0 target) [layer] (subvec without target)))]
      (assoc doc :sculpt/layers reordered))))
(defn duplicate-layer [doc id]
  (let [source (find-layer doc id)]
    (when-not source (throw (ex-info "sculpt layer not found" {:id id})))
    (let [new-id (:sculpt/next-layer-id doc) copy (assoc source :sculpt.layer/id new-id
                                                        :sculpt.layer/name (str (:sculpt.layer/name source) " Copy"))
          index (first (keep-indexed #(when (= id (:sculpt.layer/id %2)) %1) (:sculpt/layers doc)))
          at (inc index) layers (:sculpt/layers doc)]
      (-> doc (assoc :sculpt/layers (vec (concat (subvec layers 0 at) [copy] (subvec layers at)))
                     :sculpt/active-layer new-id) (update :sculpt/next-layer-id inc)))))
(defn bake-layer
  "Bake one visible layer's effective delta into the base while preserving the evaluated mesh."
  [doc id]
  (let [layer (find-layer doc id)]
    (when-not layer (throw (ex-info "sculpt layer not found" {:id id})))
    (let [base (if (:sculpt.layer/visible? layer)
                 (update (:sculpt/base doc) :positions
                         #(mapv add % (mapv (fn [d] (scale d (:sculpt.layer/opacity layer))) (:sculpt.layer/deltas layer))))
                 (:sculpt/base doc))
          zeroed (assoc layer :sculpt.layer/deltas (vec (repeat (count (:positions base)) [0.0 0.0 0.0]))
                              :sculpt.layer/opacity 1.0 :sculpt.layer/visible? true)]
      (-> doc (assoc :sculpt/base base) (update-layer id (constantly zeroed))))))
(defn apply-layer-stroke [doc b symmetry]
  (let [before (evaluate-document doc) after (apply-stroke before b symmetry)
        increment (mapv sub (:positions after) (:positions before)) active (:sculpt/active-layer doc)]
    (if (#{:mask :mask-erase} (:brush/mode b))
      (assoc-in doc [:sculpt/base :masks] (:masks after))
      (update-layer doc active update :sculpt.layer/deltas #(mapv add % increment)))))
(defn subdivide-document
  "Bake visible layers, subdivide topology, and start a fresh detail layer."
  [doc]
  (sculpt-document (subdivide-mesh (evaluate-document doc))))

(defn voxel-remesh
  "Deterministic surface voxel remesh: cluster vertices into cubic cells,
  average position/normal/mask attributes, remove degenerate and duplicate
  triangles, and compact unused vertices. Cell size is in world units."
  [mesh cell-size]
  (when-not (pos? cell-size) (throw (ex-info "remesh cell size must be positive" {:cell-size cell-size})))
  (let [positions (:positions mesh) normals (:normals mesh)
        masks (vec (or (:masks mesh) (repeat (count positions) 0.0)))
        cell #(mapv (fn [v] #?(:clj (long (Math/floor (double (/ v cell-size))))
                               :cljs (js/Math.floor (/ v cell-size)))) %)
        grouped (reduce (fn [groups index] (update groups (cell (nth positions index)) (fnil conj []) index)) {} (range (count positions)))
        ordered-cells (sort (keys grouped))
        old->cluster (reduce (fn [mapping [cluster-id key]]
                              (reduce #(assoc %1 %2 cluster-id) mapping (get grouped key))) {} (map-indexed vector ordered-cells))
        average (fn [values] (scale (reduce add [0.0 0.0 0.0] values) (/ 1.0 (count values))))
        clustered-pos (mapv #(average (map positions (get grouped %))) ordered-cells)
        clustered-normal (mapv #(normalize (average (map normals (get grouped %)))) ordered-cells)
        clustered-mask (mapv #(let [ids (get grouped %)] (/ (reduce + (map masks ids)) (count ids))) ordered-cells)
        triangles (->> (partition 3 (:indices mesh))
                       (map #(mapv old->cluster %))
                       (remove #(not= 3 (count (distinct %))))
                       (reduce (fn [{:keys [seen faces]} face]
                                 (let [canonical (vec (sort face))]
                                   (if (seen canonical) {:seen seen :faces faces}
                                     {:seen (conj seen canonical) :faces (conj faces face)}))) {:seen #{} :faces []}) :faces)
        used (vec (sort (set (mapcat identity triangles))))
        compact (zipmap used (range))]
    {:positions (mapv clustered-pos used) :normals (mapv clustered-normal used)
     :masks (mapv clustered-mask used) :indices (vec (mapcat #(map compact %) triangles))
     :remesh {:cell-size cell-size :source-vertices (count positions)
              :result-vertices (count used) :result-triangles (count triangles)}}))

(defn remesh-document
  "Bake evaluated layers into a voxel-remeshed base and start a clean layer
  whose delta cardinality exactly matches the new topology."
  [doc cell-size]
  (sculpt-document (voxel-remesh (evaluate-document doc) cell-size)))

(defn topology-diagnostics
  "Analyze indexed triangle topology for retopology/remesh validation."
  [mesh]
  (let [vertex-count (count (:positions mesh)) triangles (vec (partition 3 (:indices mesh)))
        degenerate (keep-indexed (fn [index face]
                                   (when (or (not= 3 (count (distinct face)))
                                             (some #(not (< -1 % vertex-count)) face)) index)) triangles)
        valid-faces (remove (fn [face] (or (not= 3 (count (distinct face)))
                                           (some #(not (< -1 % vertex-count)) face))) triangles)
        edges (frequencies (mapcat (fn [[a b c]] [(vec (sort [a b])) (vec (sort [b c])) (vec (sort [c a]))]) valid-faces))
        boundary (vec (sort (keep (fn [[edge count]] (when (= 1 count) edge)) edges)))
        non-manifold (vec (sort (keep (fn [[edge count]] (when (> count 2) edge)) edges)))
        used (set (mapcat identity valid-faces)) isolated (vec (remove used (range vertex-count)))
        valence (reduce (fn [result [a b]] (-> result (update a (fnil inc 0)) (update b (fnil inc 0)))) {} (keys edges))]
    {:topology/vertex-count vertex-count :topology/triangle-count (count triangles)
     :topology/boundary-edges boundary :topology/non-manifold-edges non-manifold
     :topology/degenerate-faces (vec degenerate) :topology/isolated-vertices isolated
     :topology/valence (mapv #(get valence % 0) (range vertex-count))
     :topology/manifold? (and (empty? non-manifold) (empty? degenerate) (empty? isolated))
     :topology/closed? (and (empty? boundary) (empty? non-manifold) (empty? degenerate) (empty? isolated))}))

(defn repair-topology
  "Deterministically remove invalid/degenerate/duplicate triangles and reject
  later triangles that would make any edge non-manifold, then compact all
  per-vertex attributes. Boundary holes are reported but not fabricated."
  [mesh]
  (let [vertex-count (count (:positions mesh)) source (vec (partition 3 (:indices mesh)))
        valid? #(and (= 3 (count (distinct %))) (every? (fn [i] (< -1 i vertex-count)) %))
        candidates (filter valid? source)
        accepted (reduce (fn [{:keys [faces edge-counts seen]} face]
                           (let [canonical (vec (sort face)) edges (mapv #(vec (sort %))
                                                                        [[(nth face 0) (nth face 1)]
                                                                         [(nth face 1) (nth face 2)]
                                                                         [(nth face 2) (nth face 0)]])]
                             (if (or (seen canonical) (some #(>= (get edge-counts % 0) 2) edges))
                               {:faces faces :edge-counts edge-counts :seen seen}
                               {:faces (conj faces face) :edge-counts (reduce #(update %1 %2 (fnil inc 0)) edge-counts edges)
                                :seen (conj seen canonical)})))
                         {:faces [] :edge-counts {} :seen #{}} candidates)
        faces (:faces accepted) used (vec (sort (set (mapcat identity faces)))) compact (zipmap used (range))
        masks (vec (or (:masks mesh) (repeat vertex-count 0.0)))
        repaired {:positions (mapv (:positions mesh) used) :normals (mapv (:normals mesh) used)
                  :masks (mapv masks used) :indices (vec (mapcat #(map compact %) faces))}
        diagnostics (topology-diagnostics repaired)]
    (assoc repaired :repair {:source-triangles (count source) :result-triangles (count faces)
                             :removed-triangles (- (count source) (count faces))
                             :diagnostics diagnostics})))

(defn repair-document [doc]
  "Bake layers, repair topology, and rebase to one clean layer."
  [doc]
  (sculpt-document (repair-topology (evaluate-document doc))))

(defn boundary-loops
  "Extract deterministic simple loops from boundary edges. Branching or open
  boundary graphs are rejected because an unambiguous patch cannot be made."
  [mesh]
  (let [edges (:topology/boundary-edges (topology-diagnostics mesh))
        adjacency (reduce (fn [m [a b]] (-> m (update a (fnil conj #{}) b) (update b (fnil conj #{}) a))) {} edges)]
    (when (some #(not= 2 (count %)) (vals adjacency))
      (throw (ex-info "boundary is not a set of simple closed loops" {:adjacency adjacency})))
    (loop [remaining (set edges) loops []]
      (if-let [[start next] (first (sort remaining))]
        (let [loop-vertices
              (loop [previous start current next result [start] unused remaining]
                (let [edge (vec (sort [previous current])) unused (disj unused edge) result (conj result current)]
                  (if (= current start) {:vertices (pop result) :remaining unused}
                    (let [candidate (first (sort (remove #{previous} (get adjacency current))))]
                      (when-not candidate (throw (ex-info "open boundary loop" {:at current})))
                      (recur current candidate result unused)))))]
          (recur (:remaining loop-vertices) (conj loops (:vertices loop-vertices))))
        loops))))

(defn fill-boundary-holes
  "Patch every simple boundary loop with a center fan and interpolated vertex
  attributes. Existing surface vertices/faces remain unchanged."
  [mesh]
  (let [loops (boundary-loops mesh) positions (atom (vec (:positions mesh)))
        normals (atom (vec (:normals mesh))) masks (atom (vec (or (:masks mesh) (repeat (count @positions) 0.0))))
        added (mapv (fn [loop]
                      (let [center-id (count @positions) n (count loop)
                            center (scale (reduce add [0.0 0.0 0.0] (map @positions loop)) (/ 1.0 n))
                            normal (normalize (reduce add [0.0 0.0 0.0] (map @normals loop)))
                            mask (/ (reduce + (map @masks loop)) n)]
                        (swap! positions conj center) (swap! normals conj normal) (swap! masks conj mask)
                        (vec (mapcat (fn [a b] [b a center-id]) loop (concat (rest loop) [(first loop)]))))) loops)
        result (assoc mesh :positions @positions :normals @normals :masks @masks
                     :indices (into (vec (:indices mesh)) (mapcat identity added)))
        report (topology-diagnostics result)]
    (assoc result :hole-fill {:holes (count loops) :triangles (reduce + (map count loops))
                              :closed? (:topology/closed? report)})))

(defn fill-holes-document [doc]
  (sculpt-document (fill-boundary-holes (evaluate-document doc))))
