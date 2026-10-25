(ns bim.spatial
  "Uniform-grid spatial index and deterministic LOD/stream planning for large
  BIM models. Mesh bounds are computed once when the index is built."
  (:require [bim :as bim]))

(def schema-version 2)
(defn- floor [value] (#?(:clj Math/floor :cljs js/Math.floor) value))
(defn- sqrt [value] (#?(:clj Math/sqrt :cljs js/Math.sqrt) value))

(defn element-bounds [element]
  (or (:spatial/bounds element)
      (when-let [positions (seq (:positions (bim/element-mesh element)))]
        {:min (apply mapv min positions) :max (apply mapv max positions)})))

(defn- cell-coordinate [cell-size point]
  (mapv #(long (floor (/ % cell-size))) point))

(defn- cells-for-bounds [cell-size {:keys [min max]}]
  (let [lower (cell-coordinate cell-size min) upper (cell-coordinate cell-size max)]
    (for [x (range (first lower) (inc (first upper)))
          y (range (second lower) (inc (second upper)))
          z (range (nth lower 2) (inc (nth upper 2)))] [x y z])))

(defn build-index
  ([elements] (build-index elements {}))
  ([elements {:keys [cell-size] :or {cell-size 10.0}}]
   (when-not (pos? cell-size)
     (throw (ex-info "spatial index cell size must be positive" {:cell-size cell-size})))
   (let [entries (into {}
                       (keep (fn [element]
                               (when-let [bounds (element-bounds element)]
                                 [(:id element) {:element element :bounds bounds}])))
                       elements)
         cells (reduce-kv
                (fn [result id {:keys [bounds]}]
                  (reduce #(update %1 %2 (fnil conj #{}) id)
                          result (cells-for-bounds cell-size bounds)))
                {} entries)]
     {:spatial/schema-version schema-version :spatial/cell-size cell-size
     :spatial/entries entries :spatial/cells cells})))

(defn remove-element
  "Remove one element from an index without rebuilding unaffected cells."
  [index element-id]
  (if-let [bounds (get-in index [:spatial/entries element-id :bounds])]
    (let [cells (cells-for-bounds (:spatial/cell-size index) bounds)]
      (-> (reduce (fn [result cell]
                    (let [ids (disj (get-in result [:spatial/cells cell] #{}) element-id)]
                      (if (seq ids)
                        (assoc-in result [:spatial/cells cell] ids)
                        (update result :spatial/cells dissoc cell))))
                  index cells)
          (update :spatial/entries dissoc element-id)))
    index))

(defn upsert-element
  "Insert or replace one indexed element. Precomputed `:spatial/bounds` avoids
  mesh realization and is the preferred path for streamed IFC metadata."
  [index element]
  (when-not (:id element)
    (throw (ex-info "indexed element requires an id" {:element element})))
  (if-let [bounds (element-bounds element)]
    (let [index (remove-element index (:id element))]
      (-> (reduce #(update-in %1 [:spatial/cells %2] (fnil conj #{}) (:id element))
                  index (cells-for-bounds (:spatial/cell-size index) bounds))
          (assoc-in [:spatial/entries (:id element)]
                    {:element element :bounds bounds})))
    (remove-element index (:id element))))

(defn- intersects? [left right]
  (every? true? (map (fn [left-min left-max right-min right-max]
                       (and (<= left-min right-max) (<= right-min left-max)))
                     (:min left) (:max left) (:min right) (:max right))))

(defn query-ids
  "Return exactly intersecting element ids in stable order without realizing
  geometry or copying element payloads."
  [index bounds]
  (let [ids (into #{} (mapcat #(get-in index [:spatial/cells %] #{}))
                  (cells-for-bounds (:spatial/cell-size index) bounds))]
    (->> ids
         (keep #(get-in index [:spatial/entries %]))
         (filter #(intersects? bounds (:bounds %)))
         (sort-by (comp str :id :element))
         (mapv (comp :id :element)))))

(defn query
  "Return exactly intersecting indexed elements in stable id order."
  [index bounds]
  (mapv #(get-in index [:spatial/entries % :element]) (query-ids index bounds)))

(defn query-report
  "Expose spatial culling evidence for performance gates and telemetry."
  [index bounds]
  (let [cells (vec (cells-for-bounds (:spatial/cell-size index) bounds))
        candidates (into #{} (mapcat #(get-in index [:spatial/cells %] #{})) cells)
        matches (query-ids index bounds)
        total (count (:spatial/entries index))]
    {:spatial/total-elements total :spatial/visited-cells (count cells)
     :spatial/candidate-elements (count candidates)
     :spatial/returned-elements (count matches)
     :spatial/culling-ratio (if (zero? total) 1.0
                                (- 1.0 (/ (double (count candidates)) total)))
     :spatial/element-ids matches}))

(defn nearest
  "Find the nearest indexed element AABB to a point within a search radius."
  [index point radius]
  (let [bounds {:min (mapv #(- % radius) point) :max (mapv #(+ % radius) point)}
        distance (fn [element]
                   (let [{lower :min upper :max} (get-in index [:spatial/entries (:id element) :bounds])]
                     (sqrt (reduce + (map (fn [value minimum maximum]
                                           (let [delta (cond (< value minimum) (- minimum value)
                                                             (> value maximum) (- value maximum)
                                                             :else 0.0)]
                                             (* delta delta)))
                                         point lower upper)))))]
    (when-let [candidate (first (sort-by (juxt distance (comp str :id))
                                         (query index bounds)))]
      (assoc candidate :spatial/distance (distance candidate)))))

(defn choose-lod
  "Choose :full, :coarse, or :bounds from projected AABB size in pixels."
  [bounds camera-position focal-length-px {:keys [full-threshold coarse-threshold]
                                           :or {full-threshold 80.0 coarse-threshold 12.0}}]
  (let [center (mapv #(/ (+ %1 %2) 2.0) (:min bounds) (:max bounds))
        diagonal (sqrt (reduce + (map (fn [a b] (let [delta (- b a)] (* delta delta)))
                                      (:min bounds) (:max bounds))))
        distance (max 1.0e-6
                      (sqrt (reduce + (map (fn [a b] (let [delta (- b a)] (* delta delta)))
                                           camera-position center))))
        projected (* focal-length-px (/ diagonal distance))]
    {:lod/level (cond (>= projected full-threshold) :full
                      (>= projected coarse-threshold) :coarse
                      :else :bounds)
     :lod/projected-size-px projected :lod/distance distance}))

(defn stream-plan
  "Partition visible elements into bounded batches with their requested LOD."
  ([index view-bounds camera-position focal-length-px max-batch-size]
   (stream-plan index view-bounds camera-position focal-length-px max-batch-size {}))
  ([index view-bounds camera-position focal-length-px max-batch-size
    {:keys [include-elements? lod-options] :or {include-elements? true lod-options {}}}]
   (when-not (pos? max-batch-size)
     (throw (ex-info "stream batch size must be positive" {:max-batch-size max-batch-size})))
   (->> (query-ids index view-bounds)
        (mapv (fn [id]
                (let [bounds (get-in index [:spatial/entries id :bounds])]
                  (cond-> {:element/id id :bounds bounds
                           :lod (choose-lod bounds camera-position focal-length-px
                                            lod-options)}
                    include-elements?
                    (assoc :element (get-in index [:spatial/entries id :element]))))))
        (partition-all max-batch-size)
        (map-indexed (fn [batch entries]
                       {:stream/batch batch :stream/entries (vec entries)}))
        vec)))

(defn stream-session []
  {:stream/schema-version schema-version :stream/resident {} :stream/generation 0})

(defn stream-delta
  "Reconcile a metadata-only stream plan with the resident GPU/object cache.
  Loads are distance-prioritized, LOD changes are explicit, and entries outside
  the resident budget are evicted deterministically."
  [session batches {:keys [max-resident max-loads]
                    :or {max-resident 10000 max-loads 1000}}]
  (when-not (and (pos? max-resident) (pos? max-loads))
    (throw (ex-info "stream budgets must be positive"
                    {:max-resident max-resident :max-loads max-loads})))
  (let [desired-entries (mapcat :stream/entries batches)
        priority {:full 0 :coarse 1 :bounds 2}
        ordered (sort-by (fn [entry]
                           [(get priority (get-in entry [:lod :lod/level]) 3)
                            (get-in entry [:lod :lod/distance])
                            (str (:element/id entry))]) desired-entries)
        desired (into {} (map (juxt :element/id identity)) (take max-resident ordered))
        resident (:stream/resident session)
        evict-ids (sort-by str (remove #(contains? desired %) (keys resident)))
        changed (filter (fn [[id entry]]
                          (not= (get-in resident [id :lod :lod/level])
                                (get-in entry [:lod :lod/level]))) desired)
        load-entries (->> changed (map val)
                          (sort-by (fn [entry]
                                     [(get priority (get-in entry [:lod :lod/level]) 3)
                                      (get-in entry [:lod :lod/distance])
                                      (str (:element/id entry))]))
                          (take max-loads) vec)
        loaded-ids (set (map :element/id load-entries))
        next-resident (-> (apply dissoc resident evict-ids)
                          (into (filter (fn [[id _]]
                                          (or (contains? resident id)
                                              (contains? loaded-ids id))) desired)))]
    {:stream/status (if (= (count next-resident) (count desired)) :ready :loading)
     :stream/generation (inc (:stream/generation session 0))
     :stream/load load-entries :stream/evict (vec evict-ids)
     :stream/deferred (- (count desired) (count next-resident))
     :stream/session (assoc session :stream/generation
                            (inc (:stream/generation session 0))
                            :stream/resident next-resident)}))
