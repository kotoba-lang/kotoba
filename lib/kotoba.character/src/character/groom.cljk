(ns character.groom
  "Groom: Alembic-based strand hair system for MetaHuman. Provides
  `GroomAsset` (parsed strand data), LOD decimation, strand -> hair
  card conversion, and the KAMI Groom Binary (`.kgr`) wire format.
  Restored from the legacy kami-engine/kami-character Rust crate's
  `groom.rs` (deleted in kotoba-lang/kami-engine PR #82) as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root)."
  (:require [character.math :as m]
            [character.bin :as bin]))

(defn strand [points widths root-uv group] {:points points :widths widths :root-uv root-uv :group group})

(defn groom-group [name strand-count material-slot clump-scale clump-noise]
  {:name name :strand-count strand-count :material-slot material-slot
   :clump-scale clump-scale :clump-noise clump-noise})

(defn from-kgr
  "Parse from KAMI Groom Binary (.kgr) format. Format: header(16B) +
  groups(N*var) + strand-headers(M*20B) + points(P*12B) + widths(P*4B)."
  [byte-vec]
  (when (< (count byte-vec) 16)
    (throw (ex-info "KGR too small" {})))
  (when (not= (subvec (vec byte-vec) 0 4) [0x4B 0x47 0x52 0x31]) ; "KGR1"
    (throw (ex-info "Invalid KGR magic" {})))
  (let [c0 (bin/cursor byte-vec)
        c0 (bin/seek c0 4)
        [num-groups c1] (bin/read-u32-le c0)
        [num-strands c2] (bin/read-u32-le c1)
        [num-points c3] (bin/read-u32-le c2)
        [groups c4]
        (loop [i 0 c c3 acc (transient [])]
          (if (= i num-groups)
            [(persistent! acc) c]
            (let [[name c'] (bin/read-string-le c)
                  [strand-count c''] (bin/read-u32-le c')
                  [material-slot c3'] (bin/read-u32-le c'')
                  [clump-scale c4'] (bin/read-f32-le c3')
                  [clump-noise c5'] (bin/read-f32-le c4')]
              (recur (inc i) c5' (conj! acc (groom-group name strand-count material-slot clump-scale clump-noise))))))
        [strand-headers c5]
        (loop [i 0 c c4 acc (transient [])]
          (if (= i num-strands)
            [(persistent! acc) c]
            (let [[pc c'] (bin/read-u32-le c)
                  [ru c''] (bin/read-f32-le c')
                  [rv c3'] (bin/read-f32-le c'')
                  [grp c4'] (bin/read-u32-le c3')]
              (recur (inc i) c4' (conj! acc {:point-count pc :root-uv [ru rv] :group grp})))))
        [all-points c6]
        (loop [i 0 c c5 acc (transient [])]
          (if (= i num-points)
            [(persistent! acc) c]
            (let [[x c'] (bin/read-f32-le c)
                  [y c''] (bin/read-f32-le c')
                  [z c3'] (bin/read-f32-le c'')]
              (recur (inc i) c3' (conj! acc [x y z])))))
        [all-widths _c7]
        (loop [i 0 c c6 acc (transient [])]
          (if (= i num-points)
            [(persistent! acc) c]
            (let [[w c'] (bin/read-f32-le c)]
              (recur (inc i) c' (conj! acc w)))))
        strands
        (loop [headers strand-headers pi 0 acc (transient [])]
          (if (empty? headers)
            (persistent! acc)
            (let [{:keys [point-count root-uv group]} (first headers)
                  points (subvec all-points pi (+ pi point-count))
                  widths (subvec all-widths pi (+ pi point-count))]
              (recur (rest headers) (+ pi point-count)
                     (conj! acc (strand points widths root-uv group))))))
        guide-indices (vec (range 0 num-strands 4))]
    {:strands strands :groups groups :guide-indices guide-indices :total-points num-points}))

(defn to-kgr
  "Serialize to KAMI Groom Binary (.kgr) format."
  [{:keys [strands groups]}]
  (let [num-points (reduce + (map #(count (:points %)) strands))
        out (transient [])
        out (reduce (fn [o b] (conj! o b)) out [0x4B 0x47 0x52 0x31])
        out (persistent! out)
        out (bin/write-u32-le out (count groups))
        out (bin/write-u32-le out (count strands))
        out (bin/write-u32-le out num-points)
        out (reduce
             (fn [out {:keys [name strand-count material-slot clump-scale clump-noise]}]
               (-> out
                   (bin/write-string-le name)
                   (bin/write-u32-le strand-count)
                   (bin/write-u32-le material-slot)
                   (bin/write-f32-le clump-scale)
                   (bin/write-f32-le clump-noise)))
             out groups)
        out (reduce
             (fn [out {:keys [points root-uv group]}]
               (-> out
                   (bin/write-u32-le (count points))
                   (bin/write-f32-le (nth root-uv 0))
                   (bin/write-f32-le (nth root-uv 1))
                   (bin/write-u32-le group)))
             out strands)
        out (reduce
             (fn [out {:keys [points]}]
               (reduce (fn [out [x y z]]
                         (-> out (bin/write-f32-le x) (bin/write-f32-le y) (bin/write-f32-le z)))
                       out points))
             out strands)
        out (reduce
             (fn [out {:keys [widths]}]
               (reduce bin/write-f32-le out widths))
             out strands)]
    out))

(defn decimate
  "Decimate strands to target LOD (`:full` `:half` `:quarter` `:cards`)."
  [{:keys [strands groups] :as groom} lod]
  (let [ratio (case lod :full 1.0 :half 0.5 :quarter 0.25 :cards 0.1)
        n (count strands)
        target (max 1 (int (* n ratio)))
        step (max 1 (int (Math/ceil (/ (double n) target))))
        decimated (vec (take-nth step strands))
        total-points (reduce + (map #(count (:points %)) decimated))
        guide-indices (vec (range 0 (count decimated) 4))]
    {:strands decimated :groups groups :guide-indices guide-indices :total-points total-points}))

(defn to-hair-cards
  "Convert strands to hair cards for rasterization. Each card is a quad
  strip following a cluster centroid path."
  [{:keys [strands]} cards-per-cluster]
  (let [cluster-size (max 1 (quot (count strands) (max 1 cards-per-cluster)))
        chunks (partition-all cluster-size strands)]
    (vec
     (keep
      (fn [chunk]
        (when (seq chunk)
          (let [max-points (apply max (map #(count (:points %)) chunk))]
            (when (>= max-points 2)
              (let [pairs
                    (for [pi (range max-points)]
                      (let [contributing (filter #(< pi (count (:points %))) chunk)]
                        (when (seq contributing)
                          (let [sum (reduce m/vec3+ m/vec3-zero (map #(nth (:points %) pi) contributing))
                                w-sum (reduce + (map #(nth (:widths %) pi 0.001) contributing))
                                cnt (count contributing)]
                            [(m/vec3-scale sum (/ 1.0 cnt)) (/ w-sum cnt)]))))
                    pairs (remove nil? pairs)
                    centroid-path (mapv first pairs)
                    avg-widths (mapv second pairs)
                    n (count centroid-path)]
                (when (>= n 2)
                  (let [seg-data
                        (for [i (range n)]
                          (let [tangent (cond
                                          (< (inc i) n) (m/vec3-normalize-or-zero (m/vec3- (nth centroid-path (inc i)) (nth centroid-path i)))
                                          (pos? i) (m/vec3-normalize-or-zero (m/vec3- (nth centroid-path i) (nth centroid-path (dec i))))
                                          :else [0.0 1.0 0.0])
                                normal (m/vec3-normalize-or-zero (m/vec3-cross tangent [0.0 0.0 1.0]))
                                w (* (nth avg-widths i) 2.0)
                                p (nth centroid-path i)
                                t (/ (double i) (dec n))]
                            {:pos-l (m/vec3- p (m/vec3-scale normal w))
                             :pos-r (m/vec3+ p (m/vec3-scale normal w))
                             :normal (m/vec3-normalize-or-zero (m/vec3-cross tangent normal))
                             :uv-l [0.0 t] :uv-r [1.0 t]}))
                        positions (vec (mapcat (fn [{:keys [pos-l pos-r]}] [pos-l pos-r]) seg-data))
                        normals (vec (mapcat (fn [{:keys [normal]}] [normal normal]) seg-data))
                        uvs (vec (mapcat (fn [{:keys [uv-l uv-r]}] [uv-l uv-r]) seg-data))
                        indices (vec (mapcat (fn [i]
                                                (if (pos? i)
                                                  (let [base (* (dec i) 2)]
                                                    [base (+ base 2) (+ base 1) (+ base 1) (+ base 2) (+ base 3)])
                                                  []))
                                              (range n)))]
                    {:positions positions :normals normals :uvs uvs :indices indices
                     :root-width (* (or (first avg-widths) 0.001) 2.0)
                     :atlas-index (:group (first chunk) 0)})))))))
      chunks))))

(defn to-strand-buffer
  "Build GPU-ready strand buffer for compute shader rendering. Returns
  `[points-flat offsets]` (flat xyz+width floats and strand offsets)."
  [{:keys [strands]}]
  (loop [strands strands offset 0 points-flat (transient []) offsets (transient [])]
    (if (empty? strands)
      [(persistent! points-flat) (persistent! (conj! offsets offset))]
      (let [{:keys [points widths]} (first strands)
            offsets (conj! offsets offset)
            points-flat
            (reduce
             (fn [pf i]
               (let [[x y z] (nth points i)
                     w (nth widths i 0.001)]
                 (-> pf (conj! x) (conj! y) (conj! z) (conj! w))))
             points-flat (range (count points)))]
        (recur (rest strands) (+ offset (count points)) points-flat offsets)))))
