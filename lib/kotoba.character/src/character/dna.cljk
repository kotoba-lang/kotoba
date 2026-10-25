(ns character.dna
  "MetaHuman DNA file parser — reads Epic Games `.dna` binary format
  (big-endian, u32-length-prefixed arrays, SoA Vec3 layout, vertex
  layout indirection). Restored from the legacy kami-engine/
  kami-character Rust crate's `dna.rs` (deleted in kotoba-lang/
  kami-engine PR #82) as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  Reference: <https://github.com/EpicGames/MetaHuman-DNA-Calibration>"
  (:require [character.bin :as bin]
            [character.math :as m]))

(def cm->m 0.01)

(defn soa-vec3-get [{:keys [xs ys zs]} i]
  [(nth xs i 0.0) (nth ys i 0.0) (nth zs i 0.0)])

(defn soa-vec3-len [{:keys [xs]}] (count xs))

(defn- skip-lod-mapping [c]
  (let [[lods-count c1] (bin/read-u32-be c)
        c2 (bin/seek c1 (+ (bin/pos c1) (* lods-count 2)))
        [outer c3] (bin/read-u32-be c2)]
    (loop [i 0 c c3]
      (if (= i outer)
        c
        (let [[inner c'] (bin/read-u32-be c)]
          (recur (inc i) (bin/seek c' (+ (bin/pos c') (* inner 2)))))))))

(defn- parse-descriptor [c]
  (let [[name c1] (bin/read-string-be c)
        [archetype c2] (bin/read-u16-be c1)
        [gender c3] (bin/read-u16-be c2)
        [age c4] (bin/read-u16-be c3)
        [meta-count c5] (bin/read-u32-be c4)
        [metadata c6]
        (loop [i 0 c c5 acc (transient [])]
          (if (= i meta-count)
            [(persistent! acc) c]
            (let [[k c'] (bin/read-string-be c)
                  [v c''] (bin/read-string-be c')]
              (recur (inc i) c'' (conj! acc [k v])))))
        [translation-unit c7] (bin/read-u16-be c6)
        [rotation-unit c8] (bin/read-u16-be c7)
        [cs0 c9] (bin/read-u16-be c8)
        [cs1 c10] (bin/read-u16-be c9)
        [cs2 c11] (bin/read-u16-be c10)
        [lod-count c12] (bin/read-u16-be c11)
        [max-lod c13] (bin/read-u16-be c12)
        [complexity c14] (bin/read-string-be c13)
        [db-name c15] (bin/read-string-be c14)]
    [{:name name :archetype archetype :gender gender :age age :metadata metadata
      :translation-unit translation-unit :rotation-unit rotation-unit
      :coordinate-system [cs0 cs1 cs2] :lod-count lod-count :max-lod max-lod
      :complexity complexity :db-name db-name}
     c15]))

(defn- parse-definition [c]
  (let [c (reduce (fn [c _] (skip-lod-mapping c)) c (range 4))
        [gui-control-names c1] (bin/read-array-string-be c)
        [raw-control-names c2] (bin/read-array-string-be c1)
        [joint-names c3] (bin/read-array-string-be c2)
        [blend-shape-channel-names c4] (bin/read-array-string-be c3)
        [animated-map-names c5] (bin/read-array-string-be c4)
        [mesh-names c6] (bin/read-array-string-be c5)
        [_from c7] (bin/read-array-u16-be c6)
        [_to c8] (bin/read-array-u16-be c7)
        [joint-hierarchy c9] (bin/read-array-u16-be c8)
        [neutral-joint-translations c10] (bin/read-soa-vec3-be c9)
        [neutral-joint-rotations c11] (bin/read-soa-vec3-be c10)]
    [{:joint-names joint-names :joint-hierarchy joint-hierarchy
      :neutral-joint-translations neutral-joint-translations
      :neutral-joint-rotations neutral-joint-rotations
      :blend-shape-channel-names blend-shape-channel-names
      :animated-map-names animated-map-names :mesh-names mesh-names
      :gui-control-names gui-control-names :raw-control-names raw-control-names}
     c11]))

(defn- scale-soa [soa factor]
  {:xs (mapv #(* % factor) (:xs soa)) :ys (mapv #(* % factor) (:ys soa)) :zs (mapv #(* % factor) (:zs soa))})

(defn- parse-geometry [c]
  (let [[mesh-count c1] (bin/read-u32-be c)]
    (loop [i 0 c c1 meshes (transient [])]
      (if (= i mesh-count)
        [{:meshes (persistent! meshes)} c]
        (let [[_end-offset c2] (bin/read-u32-be c)
              [positions0 c3] (bin/read-soa-vec3-be c2)
              positions (scale-soa positions0 cm->m)
              [uvs-u c4] (bin/read-array-f32-be c3)
              [uvs-v c5] (bin/read-array-f32-be c4)
              [normals c6] (bin/read-soa-vec3-be c5)
              [layout-positions c7] (bin/read-array-u32-be c6)
              [layout-uvs c8] (bin/read-array-u32-be c7)
              [layout-normals c9] (bin/read-array-u32-be c8)
              [face-count c10] (bin/read-u32-be c9)
              [faces c11]
              (loop [j 0 c c10 acc (transient [])]
                (if (= j face-count)
                  [(persistent! acc) c]
                  (let [[fv c'] (bin/read-array-u32-be c)]
                    (recur (inc j) c' (conj! acc fv)))))
              [max-influences c12] (bin/read-u16-be c11)
              [sw-count c13] (bin/read-u32-be c12)
              [skin-weights c14]
              (loop [j 0 c c13 acc (transient [])]
                (if (= j sw-count)
                  [(persistent! acc) c]
                  (let [[weights c'] (bin/read-array-f32-be c)
                        [joint-indices c''] (bin/read-array-u16-be c')]
                    (recur (inc j) c'' (conj! acc [joint-indices weights])))))
              [bs-count c15] (bin/read-u32-be c14)
              [blend-shapes c16]
              (loop [j 0 c c15 acc (transient [])]
                (if (= j bs-count)
                  [(persistent! acc) c]
                  (let [[deltas0 c'] (bin/read-soa-vec3-be c)
                        deltas (scale-soa deltas0 cm->m)
                        [vertex-indices c''] (bin/read-array-u32-be c')
                        [channel-index c3'] (bin/read-u16-be c'')]
                    (recur (inc j) c3' (conj! acc {:channel-index channel-index
                                                    :vertex-indices vertex-indices
                                                    :deltas deltas})))))
              mesh {:positions positions :uvs-u uvs-u :uvs-v uvs-v :normals normals
                    :layout-positions layout-positions :layout-uvs layout-uvs :layout-normals layout-normals
                    :faces faces :max-influences max-influences :skin-weights skin-weights
                    :blend-shapes blend-shapes}]
          (recur (inc i) c16 (conj! meshes mesh)))))))

(defn from-bytes
  "Parse a `.dna` binary file (Epic Games MetaHuman format). Returns
  `{:header :descriptor :definition :geometry}` or throws
  `ex-info` on malformed input."
  [data]
  (let [data (vec data)]
    (when (< (count data) 39)
      (throw (ex-info "DNA file too small" {})))
    (let [c (bin/cursor data)
          [b0 c1] (bin/read-u8 c)
          [b1 c2] (bin/read-u8 c1)
          [b2 c3] (bin/read-u8 c2)]
      (when-not (and (= b0 (int \D)) (= b1 (int \N)) (= b2 (int \A)))
        (throw (ex-info "Invalid DNA magic" {})))
      (let [[generation c4] (bin/read-u16-be c3)
            [version c5] (bin/read-u16-be c4)]
        (when-not (and (= generation 2) (= version 1))
          (throw (ex-info (str "Unsupported DNA version: gen=" generation " ver=" version) {})))
        (let [[descriptor-off c6] (bin/read-u32-be c5)
              [definition-off c7] (bin/read-u32-be c6)
              [behavior-off c8] (bin/read-u32-be c7)
              [controls-off c9] (bin/read-u32-be c8)
              [joints-off c10] (bin/read-u32-be c9)
              [bsc-off c11] (bin/read-u32-be c10)
              [am-off c12] (bin/read-u32-be c11)
              [geometry-off _c13] (bin/read-u32-be c12)
              section-offsets {:descriptor descriptor-off :definition definition-off
                                :behavior behavior-off :controls controls-off :joints joints-off
                                :blend-shape-channels bsc-off :animated-maps am-off :geometry geometry-off}
              header {:generation generation :version version :section-offsets section-offsets}
              [descriptor _] (parse-descriptor (bin/seek c5 descriptor-off))
              [definition _] (parse-definition (bin/seek c5 definition-off))
              [geometry _] (parse-geometry (bin/seek c5 geometry-off))]
          {:header header :descriptor descriptor :definition definition :geometry geometry})))))

(defn to-skeleton
  "Convert DNA skeleton to a `{:bones [...]}` skeleton (same shape as
  `character.body`'s bones / `kotoba-lang/skeleton`'s Bone)."
  [{:keys [definition]}]
  (let [{:keys [joint-names joint-hierarchy neutral-joint-translations neutral-joint-rotations]} definition]
    {:bones
     (vec
      (map-indexed
       (fn [i name]
         (let [parent (nth joint-hierarchy i 0xFFFF)
               t (m/vec3-scale (soa-vec3-get neutral-joint-translations i) cm->m)
               r (soa-vec3-get neutral-joint-rotations i)
               [rx ry rz] r
               rot (m/quat-from-euler-xyz (m/to-radians rx) (m/to-radians ry) (m/to-radians rz))]
           {:name name
            :parent (if (or (= parent 0xFFFF) (= parent i)) nil parent)
            :local-position t
            :local-rotation rot
            :local-scale m/vec3-one
            :inverse-bind m/mat4-identity}))
       joint-names))}))

(defn triangulate-mesh
  "Triangulate a mesh's faces and return
  `{:positions :normals :uvs :indices}` with vertex layout indirection
  resolved (quads/n-gons fan-triangulated)."
  [{:keys [geometry]} mesh-index]
  (let [{:keys [positions normals uvs-u uvs-v layout-positions layout-uvs layout-normals faces]}
        (nth (:meshes geometry) mesh-index)]
    (loop [faces faces out-positions [] out-normals [] out-uvs [] out-indices []]
      (if (empty? faces)
        {:positions out-positions :normals out-normals :uvs out-uvs :indices out-indices}
        (let [face (first faces)]
          (if (< (count face) 3)
            (recur (rest faces) out-positions out-normals out-uvs out-indices)
            (let [base (count out-positions)
                  [ps ns us]
                  (reduce
                   (fn [[ps ns us] layout-idx]
                     (let [li layout-idx
                           pi (nth layout-positions li 0)
                           ui (nth layout-uvs li 0)
                           ni (nth layout-normals li 0)]
                       [(conj ps (soa-vec3-get positions pi))
                        (conj ns (soa-vec3-get normals ni))
                        (conj us [(nth uvs-u ui 0.0) (nth uvs-v ui 0.0)])]))
                   [[] [] []] face)
                  new-indices (vec (mapcat (fn [i] [base (+ base i -1) (+ base i)]) (range 2 (count face))))]
              (recur (rest faces)
                     (into out-positions ps) (into out-normals ns) (into out-uvs us)
                     (into out-indices new-indices)))))))))

(defn mesh-name [{:keys [definition]} index] (nth (:mesh-names definition) index "unknown"))

(defn total-vertices [{:keys [geometry]}] (reduce + (map #(soa-vec3-len (:positions %)) (:meshes geometry))))
(defn total-faces [{:keys [geometry]}] (reduce + (map #(count (:faces %)) (:meshes geometry))))
(defn total-blend-shapes [{:keys [geometry]}] (reduce + (map #(count (:blend-shapes %)) (:meshes geometry))))
