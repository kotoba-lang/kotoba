(ns character.skeletal-mesh
  "Skeletal Mesh + Skeleton: MetaHuman .uasset equivalent for KAMI
  engine. KAMI Skeletal Mesh Binary (`.ksm`) — GPU-ready format for
  WebGPU skinning. Restored from the legacy kami-engine/kami-character
  Rust crate's `skeletal_mesh.rs` (deleted in kotoba-lang/kami-engine
  PR #82) as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  Skinned vertex layout (64 bytes/vertex for GPU skinning):
    position: vec3<f32> (12B), normal: vec3<f32> (12B), uv: vec2<f32> (8B),
    tangent: vec4<f32> (16B), joint-indices: vec4<u16> (8B), joint-weights: vec4<u16> (8B)."
  (:require [character.bin :as bin]
            [character.math :as m]))

(defn skinned-vertex
  [{:keys [position normal uv tangent joint-indices joint-weights]}]
  {:position position :normal normal :uv uv :tangent tangent
   :joint-indices joint-indices :joint-weights joint-weights})

(def ^:const vertex-size-bytes 64)

(defn- write-vertex [out v]
  (let [[px py pz] (:position v) [nx ny nz] (:normal v) [u vv] (:uv v)
        [tx ty tz tw] (:tangent v) [ji0 ji1 ji2 ji3] (:joint-indices v) [jw0 jw1 jw2 jw3] (:joint-weights v)]
    (-> out
        (bin/write-f32-le px) (bin/write-f32-le py) (bin/write-f32-le pz)
        (bin/write-f32-le nx) (bin/write-f32-le ny) (bin/write-f32-le nz)
        (bin/write-f32-le u) (bin/write-f32-le vv)
        (bin/write-f32-le tx) (bin/write-f32-le ty) (bin/write-f32-le tz) (bin/write-f32-le tw)
        (bin/write-u16-le ji0) (bin/write-u16-le ji1) (bin/write-u16-le ji2) (bin/write-u16-le ji3)
        (bin/write-u16-le jw0) (bin/write-u16-le jw1) (bin/write-u16-le jw2) (bin/write-u16-le jw3))))

(defn- read-vertex [c]
  (let [[px c1] (bin/read-f32-le c) [py c2] (bin/read-f32-le c1) [pz c3] (bin/read-f32-le c2)
        [nx c4] (bin/read-f32-le c3) [ny c5] (bin/read-f32-le c4) [nz c6] (bin/read-f32-le c5)
        [u c7] (bin/read-f32-le c6) [v c8] (bin/read-f32-le c7)
        [tx c9] (bin/read-f32-le c8) [ty c10] (bin/read-f32-le c9) [tz c11] (bin/read-f32-le c10) [tw c12] (bin/read-f32-le c11)
        [ji0 c13] (bin/read-u16-le c12) [ji1 c14] (bin/read-u16-le c13) [ji2 c15] (bin/read-u16-le c14) [ji3 c16] (bin/read-u16-le c15)
        [jw0 c17] (bin/read-u16-le c16) [jw1 c18] (bin/read-u16-le c17) [jw2 c19] (bin/read-u16-le c18) [jw3 c20] (bin/read-u16-le c19)]
    [{:position [px py pz] :normal [nx ny nz] :uv [u v] :tangent [tx ty tz tw]
      :joint-indices [ji0 ji1 ji2 ji3] :joint-weights [jw0 jw1 jw2 jw3]}
     c20]))

(defn from-ksm
  "Parse from KAMI Skeletal Mesh Binary (.ksm). Format: header(32B) +
  vertices(N*64B) + indices(M*4B) + lod-sections(24B each)."
  [data]
  (let [data (vec data)]
    (when (< (count data) 32) (throw (ex-info "KSM too small" {})))
    (when (not= (subvec data 0 4) [0x4B 0x53 0x4D 0x31]) ; "KSM1"
      (throw (ex-info "Invalid KSM magic" {})))
    (let [c0 (bin/seek (bin/cursor data) 4)
          [num-verts c1] (bin/read-u32-le c0)
          [num-indices c2] (bin/read-u32-le c1)
          [num-lod-sections c3] (bin/read-u32-le c2)
          [_num-morph-targets c4] (bin/read-u32-le c3)
          [_num-material-slots c5] (bin/read-u32-le c4)
          c6 (bin/seek c5 32)
          [vertices c7]
          (loop [i 0 c c6 acc (transient [])]
            (if (= i num-verts)
              [(persistent! acc) c]
              (let [[v c'] (read-vertex c)] (recur (inc i) c' (conj! acc v)))))
          [indices c8]
          (loop [i 0 c c7 acc (transient [])]
            (if (= i num-indices)
              [(persistent! acc) c]
              (let [[idx c'] (bin/read-u32-le c)] (recur (inc i) c' (conj! acc idx)))))
          [lod-sections _c9]
          (loop [i 0 c c8 acc (transient [])]
            (if (= i num-lod-sections)
              [(persistent! acc) c]
              (let [[lod-level c'] (bin/read-u32-le c)
                    [index-start c''] (bin/read-u32-le c')
                    [index-count c3'] (bin/read-u32-le c'')
                    [material-slot c4'] (bin/read-u32-le c3')
                    [vertex-start c5'] (bin/read-u32-le c4')
                    [vertex-count c6'] (bin/read-u32-le c5')]
                (recur (inc i) c6' (conj! acc {:lod-level lod-level :index-start index-start
                                                :index-count index-count :material-slot material-slot
                                                :vertex-start vertex-start :vertex-count vertex-count})))))
          [bmin bmax]
          (reduce (fn [[bmin bmax] {:keys [position]}]
                    [(mapv min bmin position) (mapv max bmax position)])
                  [[Double/MAX_VALUE Double/MAX_VALUE Double/MAX_VALUE]
                   [(- Double/MAX_VALUE) (- Double/MAX_VALUE) (- Double/MAX_VALUE)]]
                  vertices)]
      {:vertices vertices :indices indices :lod-sections lod-sections
       :morph-targets [] :material-slots [] :skeleton nil
       :bounds-min (if (empty? vertices) m/vec3-zero bmin)
       :bounds-max (if (empty? vertices) m/vec3-zero bmax)})))

(defn to-ksm
  "Serialize to KAMI Skeletal Mesh Binary (.ksm)."
  [{:keys [vertices indices lod-sections morph-targets material-slots]}]
  (let [out []
        out (-> out
                (bin/write-bytes [0x4B 0x53 0x4D 0x31])
                (bin/write-u32-le (count vertices))
                (bin/write-u32-le (count indices))
                (bin/write-u32-le (count lod-sections))
                (bin/write-u32-le (count morph-targets))
                (bin/write-u32-le (count material-slots))
                (bin/write-bytes (repeat 8 0)))
        out (reduce write-vertex out vertices)
        out (reduce bin/write-u32-le out indices)
        out (reduce (fn [out {:keys [lod-level index-start index-count material-slot vertex-start vertex-count]}]
                      (-> out
                          (bin/write-u32-le lod-level)
                          (bin/write-u32-le index-start)
                          (bin/write-u32-le index-count)
                          (bin/write-u32-le material-slot)
                          (bin/write-u32-le vertex-start)
                          (bin/write-u32-le vertex-count)))
                    out lod-sections)]
    out))

(defn lod-indices
  "Get indices for a specific LOD level."
  [{:keys [lod-sections indices]} lod]
  (if-let [sec (first (filter #(= (:lod-level %) lod) lod-sections))]
    (let [start (:index-start sec)
          end (min (count indices) (+ start (:index-count sec)))]
      (subvec (vec indices) start end))
    (vec indices)))

(defn apply-morph
  "Apply a morph target at given weight (0.0-1.0). Returns modified
  vertex vector (leaves `vertices` untouched)."
  [{:keys [vertices morph-targets]} target-name weight]
  (if-let [target (first (filter #(= (:name %) target-name) morph-targets))]
    (reduce
     (fn [verts {:keys [vertex-index position-delta normal-delta]}]
       (if (< vertex-index (count verts))
         (update verts vertex-index
                 (fn [v]
                   (-> v
                       (update :position #(m/vec3+ % (m/vec3-scale position-delta weight)))
                       (update :normal #(m/vec3+ % (m/vec3-scale normal-delta weight))))))
         verts))
     (vec vertices) (:deltas target))
    (vec vertices)))

(defn triangle-count [{:keys [indices]}] (quot (count indices) 3))

(defn skinned-vertex-buffer-layout
  "GPU skinning vertex buffer layout descriptor: `[byte-offset shader-location wgsl-format]`."
  []
  [[0 0 "float32x3"]
   [12 1 "float32x3"]
   [24 2 "float32x2"]
   [32 3 "float32x4"]
   [48 4 "uint16x4"]
   [56 5 "uint16x4"]])
