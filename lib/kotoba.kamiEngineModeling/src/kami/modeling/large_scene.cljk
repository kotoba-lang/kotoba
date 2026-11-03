(ns kami.modeling.large-scene
  "Out-of-core scene planning: shared geometry, instances, BVH, frustum culling,
  LOD selection and deterministic content-addressed chunk residency."
  (:require [kami.modeling.document :as document]))

(defn- vec3? [v] (and (vector? v) (= 3 (count v)) (every? number? v)))
(defn- v+ [a b] (mapv + a b))
(defn- v- [a b] (mapv - a b))
(defn- dot [a b] (reduce + (map * a b)))
(defn- center [bounds] (mapv #(/ (+ %1 %2) 2.0) (:min bounds) (:max bounds)))
(defn- extent [bounds] (mapv - (:max bounds) (:min bounds)))
(defn- union-bounds [bounds]
  {:min (apply mapv min (map :min bounds)) :max (apply mapv max (map :max bounds))})

(defn geometry [id lods bounds bytes]
  (when-not (and (uuid? id) (seq lods) (vec3? (:min bounds)) (vec3? (:max bounds))
                 (every? true? (map < (:min bounds) (:max bounds))) (integer? bytes) (pos? bytes)
                 (every? #(and (integer? (:lod/level %)) (integer? (:lod/triangles %))
                               (pos? (:lod/triangles %)) (number? (:lod/max-distance %))) lods))
    (throw (ex-info "invalid shared geometry" {:id id})))
  {:geometry/id id :geometry/lods (vec (sort-by :lod/level lods))
   :geometry/bounds bounds :geometry/bytes bytes})

(defn instance [id geometry-id translation]
  (when-not (and (uuid? id) (uuid? geometry-id) (vec3? translation))
    (throw (ex-info "invalid scene instance" {:id id})))
  (let [picking-id (reduce (fn [h ch]
                             #?(:clj (bit-and 0xffffff (unchecked-add-int (unchecked-multiply-int 31 (int h)) (int ch)))
                                :cljs (bit-and 0xffffff (+ (* 31 h) (int ch))))) 17 (str id))]
    {:instance/id id :instance/geometry geometry-id :instance/translation translation
     :instance/picking-id picking-id}))

(defn instance-bounds [geometries instance]
  (let [bounds (get-in geometries [(:instance/geometry instance) :geometry/bounds])
        t (:instance/translation instance)]
    (when-not bounds (throw (ex-info "instance geometry missing" {:instance (:instance/id instance)})))
    {:min (v+ (:min bounds) t) :max (v+ (:max bounds) t)}))

(defn build-bvh
  ([geometries instances] (build-bvh geometries instances 8))
  ([geometries instances leaf-size]
   (when-not (and (pos? leaf-size) (seq instances)) (throw (ex-info "BVH requires instances" {})))
   (letfn [(build [items]
             (let [with-bounds (mapv #(assoc % ::bounds (instance-bounds geometries %)) items)
                   bounds (union-bounds (map ::bounds with-bounds))]
               (if (<= (count items) leaf-size)
                 {:bvh/bounds bounds :bvh/instances (mapv #(dissoc % ::bounds) with-bounds)}
                 (let [axis (first (apply max-key second (map-indexed vector (extent bounds))))
                       sorted (vec (sort-by #(nth (center (::bounds %)) axis) with-bounds))
                       split (quot (count sorted) 2)]
                   {:bvh/bounds bounds :bvh/axis axis
                    :bvh/children [(build (mapv #(dissoc % ::bounds) (subvec sorted 0 split)))
                                   (build (mapv #(dissoc % ::bounds) (subvec sorted split)))]}))))]
     (build (vec instances)))))

(defn frustum [planes]
  (when-not (and (= 6 (count planes))
                 (every? #(and (vec3? (:normal %)) (number? (:distance %))) planes))
    (throw (ex-info "frustum requires six normalized planes" {})))
  {:frustum/planes (vec planes)})

(defn- bounds-visible? [frustum bounds]
  (every? (fn [{:keys [normal distance]}]
            (let [positive (mapv (fn [n lo hi] (if (neg? n) lo hi)) normal (:min bounds) (:max bounds))]
              (>= (+ (dot normal positive) distance) 0))) (:frustum/planes frustum)))

(defn visible-instances [geometries bvh frustum]
  (letfn [(visit [node]
            (if-not (bounds-visible? frustum (:bvh/bounds node)) []
              (if-let [items (:bvh/instances node)]
                (filterv #(bounds-visible? frustum (instance-bounds geometries %)) items)
                (mapcat visit (:bvh/children node)))))]
    (vec (visit bvh))))

(defn select-lod [geometry camera-position instance]
  (let [p (:instance/translation instance) delta (v- p camera-position)
        distance (#?(:clj Math/sqrt :cljs js/Math.sqrt) (dot delta delta))
        lods (:geometry/lods geometry)]
    (or (first (filter #(<= distance (:lod/max-distance %)) lods)) (last lods))))

(defn chunk-id [chunk-size translation]
  (mapv #(long (#?(:clj Math/floor :cljs js/Math.floor) (/ % chunk-size))) translation))

(defn spatial-chunks [instances chunk-size]
  (when-not (pos? chunk-size) (throw (ex-info "chunk size must be positive" {})))
  (into (sorted-map) (map (fn [[id xs]] [id (vec (sort-by (comp str :instance/id) xs))])
                           (group-by #(chunk-id chunk-size (:instance/translation %)) instances))))

(defn streaming-plan [geometries visible camera-position resident-geometry-ids byte-budget]
  (let [groups (group-by :instance/geometry visible)
        candidates (mapv (fn [[geometry-id instances]]
                           (let [geometry (get geometries geometry-id)
                                 nearest (apply min-key (fn [i]
                                                          (let [d (v- (:instance/translation i) camera-position)] (dot d d))) instances)]
                             {:geometry/id geometry-id :geometry/bytes (:geometry/bytes geometry)
                              :priority/distance-squared (let [d (v- (:instance/translation nearest) camera-position)] (dot d d))
                              :instances instances})) groups)
        ordered (sort-by (juxt #(not (contains? resident-geometry-ids (:geometry/id %)))
                               :priority/distance-squared (comp str :geometry/id)) candidates)]
    (loop [remaining ordered used 0 selected [] rejected []]
      (if-let [candidate (first remaining)]
        (let [already? (contains? resident-geometry-ids (:geometry/id candidate))
              cost (if already? 0 (:geometry/bytes candidate))]
          (if (<= (+ used cost) byte-budget)
            (recur (rest remaining) (+ used cost) (conj selected candidate) rejected)
            (recur (rest remaining) used selected (conj rejected candidate))))
        {:stream/selected selected :stream/deferred rejected :stream/upload-bytes used
         :stream/draws (mapv (fn [candidate]
                               {:geometry/id (:geometry/id candidate)
                                :instance-count (count (:instances candidate))
                                :lods (frequencies (map #(-> (select-lod (get geometries (:geometry/id candidate)) camera-position %)
                                                            :lod/level) (:instances candidate)))}) selected)}))))

(defn procedural-grid-manifest
  "Out-of-core occurrence manifest. Stores chunk descriptors, never a million
  occurrence maps, while preserving deterministic IDs and exact counts."
  [id geometry-id columns rows spacing chunk-columns chunk-rows triangles-per-instance]
  (when-not (and (uuid? id) (uuid? geometry-id) (every? pos-int? [columns rows chunk-columns chunk-rows])
                 (pos? spacing) (pos-int? triangles-per-instance))
    (throw (ex-info "invalid procedural grid manifest" {})))
  (let [chunks-x (long (#?(:clj Math/ceil :cljs js/Math.ceil) (/ columns chunk-columns)))
        chunks-y (long (#?(:clj Math/ceil :cljs js/Math.ceil) (/ rows chunk-rows)))
        descriptors (vec (for [cy (range chunks-y) cx (range chunks-x)
                               :let [x0 (* cx chunk-columns) y0 (* cy chunk-rows)
                                     width (min chunk-columns (- columns x0))
                                     height (min chunk-rows (- rows y0))]]
                           {:chunk/id [cx cy] :chunk/origin [x0 y0] :chunk/size [width height]
                            :chunk/occurrences (* width height)}))]
    {:manifest/id id :manifest/geometry geometry-id :manifest/columns columns :manifest/rows rows
     :manifest/spacing spacing :manifest/chunk-size [chunk-columns chunk-rows]
     :manifest/chunks descriptors :manifest/occurrences (* columns rows)
     :manifest/triangles (* columns rows triangles-per-instance)
     :manifest/triangles-per-instance triangles-per-instance}))

(defn materialize-chunks [manifest chunk-ids]
  (let [wanted (set chunk-ids) geometry-id (:manifest/geometry manifest) spacing (:manifest/spacing manifest)]
    (vec (mapcat (fn [{:chunk/keys [id origin size]}]
                   (when (wanted id)
                     (let [[x0 y0] origin [width height] size]
                       (for [dy (range height) dx (range width)
                             :let [x (+ x0 dx) y (+ y0 dy)]]
                         (instance (document/stable-uuid (:manifest/id manifest) (str x "/" y))
                                   geometry-id [(* spacing x) 0 (* spacing y)])))))
                 (:manifest/chunks manifest)))))

(defn manifest-metrics [manifest resident-chunk-ids]
  (let [resident (filter (comp (set resident-chunk-ids) :chunk/id) (:manifest/chunks manifest))
        occurrences (reduce + (map :chunk/occurrences resident))]
    {:scene/total-occurrences (:manifest/occurrences manifest)
     :scene/total-triangles (:manifest/triangles manifest)
     :scene/resident-occurrences occurrences
     :scene/resident-triangles (* occurrences (:manifest/triangles-per-instance manifest))
     :scene/resident-chunks (count resident)}))

(defn device-report
  [device backend {:keys [first-useful-frame-ms p95-frame-ms max-main-thread-stall-ms
                          cpu-memory-bytes gpu-memory-bytes visible-occurrences resident-triangles
                          picking-ids provenance-revision]}]
  (when-not (and (string? device) (seq device) (#{:webgpu :webgl2} backend)
                 (every? #(and (number? %) (not (neg? %)))
                         [first-useful-frame-ms p95-frame-ms max-main-thread-stall-ms
                          cpu-memory-bytes gpu-memory-bytes])
                 (every? pos-int? [visible-occurrences resident-triangles])
                 (vector? picking-ids) (every? integer? picking-ids)
                 (= (count picking-ids) (count (distinct picking-ids)))
                 (string? provenance-revision) (seq provenance-revision))
    (throw (ex-info "invalid named-device performance report" {:device device :backend backend})))
  {:report/device device :report/backend backend
   :report/first-useful-frame-ms first-useful-frame-ms :report/p95-frame-ms p95-frame-ms
   :report/max-main-thread-stall-ms max-main-thread-stall-ms
   :report/cpu-memory-bytes cpu-memory-bytes :report/gpu-memory-bytes gpu-memory-bytes
   :report/visible-occurrences visible-occurrences :report/resident-triangles resident-triangles
   :report/picking-ids picking-ids :report/provenance-revision provenance-revision})

(defn performance-gate
  "Evaluate the ADR named-device matrix. Each device must report both backends;
  backend picking IDs and source provenance must be identical."
  [reports {:keys [max-first-frame-ms max-p95-frame-ms max-stall-ms max-cpu-memory-bytes
                   max-gpu-memory-bytes min-visible-occurrences min-resident-triangles]}]
  (let [by-device (group-by :report/device reports)
        violations
        (vec
         (concat
          (for [[device rs] by-device
                :when (not= #{:webgpu :webgl2} (set (map :report/backend rs)))]
            {:error :missing-backend :device device})
          (mapcat
           (fn [[device rs]]
             (let [by-backend (into {} (map (juxt :report/backend identity) rs))
                   webgpu (:webgpu by-backend) webgl2 (:webgl2 by-backend)]
               (concat
                (when (and webgpu webgl2
                           (not= (:report/picking-ids webgpu) (:report/picking-ids webgl2)))
                  [{:error :picking-parity :device device}])
                (when (and webgpu webgl2
                           (not= (:report/provenance-revision webgpu) (:report/provenance-revision webgl2)))
                  [{:error :provenance-parity :device device}])
                (mapcat
                 (fn [r]
                   (keep identity
                         [(when (> (:report/first-useful-frame-ms r) max-first-frame-ms)
                            {:error :first-frame-budget :device device :backend (:report/backend r)})
                          (when (> (:report/p95-frame-ms r) max-p95-frame-ms)
                            {:error :frame-time-budget :device device :backend (:report/backend r)})
                          (when (> (:report/max-main-thread-stall-ms r) max-stall-ms)
                            {:error :main-thread-stall-budget :device device :backend (:report/backend r)})
                          (when (> (:report/cpu-memory-bytes r) max-cpu-memory-bytes)
                            {:error :cpu-memory-budget :device device :backend (:report/backend r)})
                          (when (> (:report/gpu-memory-bytes r) max-gpu-memory-bytes)
                            {:error :gpu-memory-budget :device device :backend (:report/backend r)})
                          (when (< (:report/visible-occurrences r) min-visible-occurrences)
                            {:error :visible-occurrence-floor :device device :backend (:report/backend r)})
                          (when (< (:report/resident-triangles r) min-resident-triangles)
                            {:error :resident-triangle-floor :device device :backend (:report/backend r)})])) rs))))
           by-device)))]
    {:gate/pass? (and (seq reports) (empty? violations)) :gate/devices (vec (sort (keys by-device)))
     :gate/reports (count reports) :gate/violations violations}))
