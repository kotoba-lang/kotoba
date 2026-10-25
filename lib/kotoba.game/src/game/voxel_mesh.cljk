(ns game.voxel-mesh
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-game Rust
  crate (`kami-game/src/voxel_mesh.rs`, 1205 lines, `kotoba-lang/kami-engine`,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of the
  clj-wgsl migration (ADR-2607010930, `com-junkawasaki/root`). Restored as part
  of a 7-cluster parallel restoration of `kami-game` — this is Cluster D
  (procedural mesh generation).

  Purpose: voxel-to-mesh conversion — naive per-face meshing, greedy meshing
  (merges coplanar same-block faces into larger quads, chunk-neighbor-aware
  boundary culling), LOD downsampling (majority-vote block reduction), and a
  world-space `offset-positions` transform that avoids floating-point seams
  at chunk boundaries.

  The original `voxel_mesh.rs` was `use crate::voxel::{BlockType, CHUNK_SIZE,
  VoxelChunk}` — i.e. it depended on a *different* in-crate `voxel.rs` module
  (a `BlockType` enum of 16 material kinds + a dense `VoxelChunk`), not the
  already-restored `kotoba-lang/voxel` repo (which ports a *different* Rust
  crate, `kami-voxel`, with a `Voxel{material,color}` + `Volume` trait
  abstraction — different shape entirely). Since `kami-game/src/voxel.rs`
  itself belongs to a different restoration cluster and its source was not
  fetched here, this namespace inlines a small **local duck-typed shim**
  (`chunk-size`, `block-order`/`block-index?`, `solid?`/`transparent?`,
  `chunk-new`/`chunk-solid`/`chunk-get`/`chunk-set`, `default-palette`) below
  — documented, minimal, and matching only what the ported functions/tests
  need (16 material kinds incl. air, `is_solid`/`is_transparent` semantics
  exercised by the original tests). No hard dependency on another cluster's
  repo; if/when `kami-game/src/voxel.rs` is restored as `game.voxel`, this
  shim can be swapped for a `:require` of it without changing the mesher
  logic below.

  A *mesh* here is `{:vertices [floats, interleaved pos3+norm3+uv2+color4 per
  vertex, stride 12] :indices [ints] :vertex-count int :index-count int}`,
  mirroring the original `struct VoxelMesh`. Pure data + pure functions
  throughout; no IO/GPU. `offset-positions` is a pure transform here (the
  original mutated `&mut self`; CLJC data is immutable, so it returns a new
  mesh instead).")

;; ---------------------------------------------------------------------------
;; Local voxel duck-type shim (see docstring above)
;; ---------------------------------------------------------------------------

(def chunk-size
  "Chunk edge length in blocks. Mirrors `CHUNK_SIZE`."
  16)

(def block-order
  "16 material kinds (index 0..15), index-compatible with the original's
  `BlockType as usize` / `counts: [u32; 16]` arrays. Mirrors `enum BlockType`."
  [:air :dirt :grass :stone :water :sand :wood :leaf
   :ore :brick :glass :metal :snow :lava :ice :gravel])

(def ^:private block-index
  (into {} (map-indexed (fn [i k] [k i]) block-order)))

(defn block-from-index
  "Mirrors `BlockType::from_u8`."
  [i]
  (nth block-order i))

(defn solid?
  "A block is solid iff it isn't air. Mirrors `BlockType::is_solid`."
  [block]
  (not= block :air))

(def ^:private transparent-blocks
  "Documented assumption (original `is_transparent` impl not recovered here):
  only :water and :glass are asserted transparent — this is exactly what the
  ported tests (`transparent_block_culling_asymmetry`,
  `two_transparent_blocks_keep_shared_faces`) exercise. :leaf/:ice are
  plausibly transparent in the original too, but left opaque since no test
  pins that behavior."
  #{:water :glass})

(defn transparent?
  "Mirrors `BlockType::is_transparent`."
  [block]
  (contains? transparent-blocks block))

(defn default-palette
  "16-entry vector of `[r g b a]` colors, indexed like `block-order`. Mirrors
  `default_palette()`."
  []
  (mapv (fn [i]
          (let [t (/ (double i) 15.0)]
            [t (- 1.0 t) 0.5 1.0]))
        (range 16)))

(defn- chunk-index [x y z]
  (+ (* y chunk-size chunk-size) (* z chunk-size) x))

(defn chunk-new
  "New chunk, all cells air. Mirrors `VoxelChunk::new`."
  []
  {:blocks (vec (repeat (* chunk-size chunk-size chunk-size) :air))})

(defn chunk-solid
  "New chunk, every cell set to `block`. Mirrors `VoxelChunk::solid`."
  [block]
  {:blocks (vec (repeat (* chunk-size chunk-size chunk-size) block))})

(defn chunk-get
  "Mirrors `VoxelChunk::get`."
  [chunk x y z]
  (nth (:blocks chunk) (chunk-index x y z)))

(defn chunk-set
  "Mirrors `VoxelChunk::set` (functional: returns a new chunk)."
  [chunk x y z block]
  (update chunk :blocks assoc (chunk-index x y z) block))

;; ---------------------------------------------------------------------------
;; Portable math helper
;; ---------------------------------------------------------------------------

(defn- abs* [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))

;; ---------------------------------------------------------------------------
;; VoxelMesh
;; ---------------------------------------------------------------------------

(def ^:private vertex-stride 12)

(defn offset-positions
  "Return a new mesh with `offset` (`[dx dy dz]`) added to every vertex
  position. Shifts every vertex position by `offset` so that vertices are in
  world coordinates, eliminating floating-point seams at chunk boundaries
  (integer chunk offsets added to small integer local coords keep full f32
  precision instead of relying on matrix multiplication). Pure (original
  mutated `&mut self`). Mirrors `VoxelMesh::offset_positions`."
  [mesh [dx dy dz]]
  (let [n (:vertex-count mesh)
        verts (reduce (fn [v i]
                         (let [base (* i vertex-stride)]
                           (-> v
                               (update base + dx)
                               (update (+ base 1) + dy)
                               (update (+ base 2) + dz))))
                       (:vertices mesh) (range n))]
    (assoc mesh :vertices verts)))

;; ---------------------------------------------------------------------------
;; Face direction
;; ---------------------------------------------------------------------------

(def ^:private face-normals
  {:pos-x [1.0 0.0 0.0] :neg-x [-1.0 0.0 0.0]
   :pos-y [0.0 1.0 0.0] :neg-y [0.0 -1.0 0.0]
   :pos-z [0.0 0.0 1.0] :neg-z [0.0 0.0 -1.0]})

(defn face-normal
  "Mirrors `Face::normal`."
  [face]
  (get face-normals face))

;; ---------------------------------------------------------------------------
;; Naive meshing
;; ---------------------------------------------------------------------------

(def ^:private quad-uvs [[0.0 0.0] [1.0 0.0] [1.0 1.0] [0.0 1.0]])

(defn- face-corners [face x y z]
  (case face
    :pos-x [[(+ x 1.0) y z] [(+ x 1.0) y (+ z 1.0)] [(+ x 1.0) (+ y 1.0) (+ z 1.0)] [(+ x 1.0) (+ y 1.0) z]]
    :neg-x [[x y (+ z 1.0)] [x y z] [x (+ y 1.0) z] [x (+ y 1.0) (+ z 1.0)]]
    :pos-y [[x (+ y 1.0) z] [(+ x 1.0) (+ y 1.0) z] [(+ x 1.0) (+ y 1.0) (+ z 1.0)] [x (+ y 1.0) (+ z 1.0)]]
    :neg-y [[x y (+ z 1.0)] [(+ x 1.0) y (+ z 1.0)] [(+ x 1.0) y z] [x y z]]
    :pos-z [[x y (+ z 1.0)] [(+ x 1.0) y (+ z 1.0)] [(+ x 1.0) (+ y 1.0) (+ z 1.0)] [x (+ y 1.0) (+ z 1.0)]]
    :neg-z [[(+ x 1.0) y z] [x y z] [x (+ y 1.0) z] [(+ x 1.0) (+ y 1.0) z]]))

(defn- emit-face
  "Emit a single face quad (4 vertices, 6 indices). Mirrors `emit_face`."
  [[vertices indices] x y z face color]
  (let [base (quot (count vertices) vertex-stride)
        n (face-normal face)
        corners (face-corners face x y z)
        vertices' (reduce (fn [v i]
                             (-> v
                                 (into (nth corners i))
                                 (into n)
                                 (into (nth quad-uvs i))
                                 (into color)))
                           vertices (range 4))
        indices' (into indices [base (inc base) (+ base 2) base (+ base 2) (+ base 3)])]
    [vertices' indices']))

(defn- emit-quad
  "Emit a greedy-merged quad at arbitrary origin with du/dv extents. Mirrors
  `emit_quad`."
  [[vertices indices] origin du dv normal color positive?]
  (let [p0 origin
        p1 (mapv + origin du)
        p2 (mapv + origin du dv)
        p3 (mapv + origin dv)
        corners (if positive? [p0 p1 p2 p3] [p1 p0 p3 p2])
        base (quot (count vertices) vertex-stride)
        vertices' (reduce (fn [v i]
                             (-> v
                                 (into (nth corners i))
                                 (into normal)
                                 (into (nth quad-uvs i))
                                 (into color)))
                           vertices (range 4))
        indices' (into indices [base (inc base) (+ base 2) base (+ base 2) (+ base 3)])]
    [vertices' indices']))

(defn- ->voxel-mesh [[vertices indices]]
  {:vertices vertices
   :indices indices
   :vertex-count (quot (count vertices) vertex-stride)
   :index-count (count indices)})

(defn naive-mesh
  "Naive meshing: one quad per exposed face. Simple but more vertices.
  Mirrors `naive_mesh`."
  [chunk palette]
  (->voxel-mesh
   (reduce
    (fn [acc [x y z]]
      (let [block (chunk-get chunk x y z)]
        (if-not (solid? block)
          acc
          (let [color (get palette (get block-index block) [1.0 1.0 1.0 1.0])
                fx (double x) fy (double y) fz (double z)
                neighbors [[:pos-x (if (< (inc x) chunk-size) (chunk-get chunk (inc x) y z) :air)]
                           [:neg-x (if (> x 0) (chunk-get chunk (dec x) y z) :air)]
                           [:pos-y (if (< (inc y) chunk-size) (chunk-get chunk x (inc y) z) :air)]
                           [:neg-y (if (> y 0) (chunk-get chunk x (dec y) z) :air)]
                           [:pos-z (if (< (inc z) chunk-size) (chunk-get chunk x y (inc z)) :air)]
                           [:neg-z (if (> z 0) (chunk-get chunk x y (dec z)) :air)]]]
            (reduce (fn [acc [face neighbor]]
                      (if (and (solid? neighbor) (not (transparent? neighbor)))
                        acc
                        (emit-face acc fx fy fz face color)))
                    acc neighbors)))))
    [[] []]
    (for [y (range chunk-size) z (range chunk-size) x (range chunk-size)] [x y z]))))

;; ---------------------------------------------------------------------------
;; Greedy meshing
;; ---------------------------------------------------------------------------

(def chunk-neighbors-default
  "Mirrors `ChunkNeighbors::default` — all six boundary slices absent (no
  neighbor => chunk edge treated as air)."
  {:pos-x nil :neg-x nil :pos-y nil :neg-y nil :pos-z nil :neg-z nil})

(defn- neighbor-key [axis positive?]
  (case [axis positive?]
    [0 true] :pos-x [0 false] :neg-x
    [1 true] :pos-y [1 false] :neg-y
    [2 true] :pos-z [2 false] :neg-z))

(defn- axis-face [axis positive?]
  (case [axis positive?]
    [0 true] :pos-x [0 false] :neg-x
    [1 true] :pos-y [1 false] :neg-y
    [2 true] :pos-z [2 false] :neg-z))

(defn- pos3 [axis d u-axis u v-axis v]
  (let [p (vec (repeat 3 0))]
    (-> p (assoc axis d) (assoc u-axis u) (assoc v-axis v))))

(defn greedy-mesh-with-neighbors
  "Greedy meshing with neighbor-aware boundary culling: merges coplanar
  adjacent faces of the same block type into larger quads. Faces at chunk
  boundaries are only generated if the neighbor block is air/transparent.
  Mirrors `greedy_mesh_with_neighbors`."
  [chunk palette neighbors]
  (let [s chunk-size]
    (->voxel-mesh
     (reduce
      (fn [acc axis]
        (let [[u-axis v-axis] (case axis 0 [1 2] 1 [0 2] [0 1])]
          (reduce
           (fn [acc positive?]
             (reduce
              (fn [acc d]
                (let [mask (vec (repeat s (vec (repeat s :air))))
                      mask (reduce
                            (fn [mask [v u]]
                              (let [[x y z] (pos3 axis d u-axis u v-axis v)
                                    block (chunk-get chunk x y z)]
                                (if-not (solid? block)
                                  mask
                                  (let [nd (if positive? (inc d) (dec d))
                                        neighbor (if (and (>= nd 0) (< nd s))
                                                   (let [[nx ny nz] (pos3 axis nd u-axis u v-axis v)]
                                                     (chunk-get chunk nx ny nz))
                                                   (if-let [slice (get neighbors (neighbor-key axis positive?))]
                                                     (nth slice (+ (* v chunk-size) u))
                                                     :air))]
                                    (if (or (not (solid? neighbor)) (transparent? neighbor))
                                      (assoc-in mask [v u] block)
                                      mask)))))
                            mask
                            (for [v (range s) u (range s)] [v u]))
                      visited (vec (repeat s (vec (repeat s false))))]
                  (loop [acc acc, visited visited, v 0, u 0]
                    (cond
                      (>= v s) acc
                      (>= u s) (recur acc visited (inc v) 0)
                      (or (get-in visited [v u]) (= (get-in mask [v u]) :air))
                      (recur acc visited v (inc u))
                      :else
                      (let [block (get-in mask [v u])
                            w (loop [w 1]
                                (if (and (< (+ u w) s)
                                         (= (get-in mask [v (+ u w)]) block)
                                         (not (get-in visited [v (+ u w)])))
                                  (recur (inc w))
                                  w))
                            h (loop [h 1]
                                (if (and (< (+ v h) s)
                                         (every? (fn [du] (and (= (get-in mask [(+ v h) (+ u du)]) block)
                                                                (not (get-in visited [(+ v h) (+ u du)]))))
                                                 (range w)))
                                  (recur (inc h))
                                  h))
                            visited' (reduce (fn [vis dv]
                                                (reduce (fn [vis du] (assoc-in vis [(+ v dv) (+ u du)] true))
                                                        vis (range w)))
                                              visited (range h))
                            color (get palette (get block-index block) [1.0 1.0 1.0 1.0])
                            face (axis-face axis positive?)
                            origin (-> (vec (repeat 3 0.0))
                                       (assoc axis (double (if positive? (inc d) d)))
                                       (assoc u-axis (double u))
                                       (assoc v-axis (double v)))
                            du-vec (assoc (vec (repeat 3 0.0)) u-axis (double w))
                            dv-vec (assoc (vec (repeat 3 0.0)) v-axis (double h))
                            acc' (emit-quad acc origin du-vec dv-vec (face-normal face) color positive?)]
                        (recur acc' visited' v (+ u w)))))))
              acc (range s)))
           acc [true false])))
      [[] []]
      (range 3)))))

(defn greedy-mesh
  "Greedy meshing with no neighbor data (chunk edges treated as air).
  Mirrors `greedy_mesh`."
  [chunk palette]
  (greedy-mesh-with-neighbors chunk palette chunk-neighbors-default))

;; ---------------------------------------------------------------------------
;; LOD (level-of-detail) downsampling
;; ---------------------------------------------------------------------------

(defn- downsample-majority
  "Down-sample a chunk by `factor` (2 or 4) using majority-vote of each
  sub-block. Returns `[data size]` where `data` is a flat `size^3` vector of
  block-index bytes. Mirrors `downsample_majority`."
  [chunk factor]
  (let [size (quot chunk-size factor)
        idx (fn [gx gy gz] (+ (* gy size size) (* gz size) gx))
        data (vec (repeat (* size size size) 0))
        data' (reduce
               (fn [data [gy gz gx]]
                 (let [counts (reduce
                               (fn [counts [dy dz dx]]
                                 (let [b (chunk-get chunk (+ (* gx factor) dx) (+ (* gy factor) dy) (+ (* gz factor) dz))]
                                   (if (solid? b)
                                     (update counts (get block-index b) (fnil inc 0))
                                     counts)))
                               {}
                               (for [dy (range factor) dz (range factor) dx (range factor)] [dy dz dx]))
                       [best _] (reduce (fn [[best-i best-c] i]
                                          (let [c (get counts i 0)]
                                            (if (> c best-c) [i c] [best-i best-c])))
                                        [0 0] (range 16))]
                   (assoc data (idx gx gy gz) best)))
               data
               (for [gy (range size) gz (range size) gx (range size)] [gy gz gx]))]
    [data' size]))

(defn- greedy-mesh-reduced
  "Greedy mesh a reduced grid (size < chunk-size) packed into a flat block-
  index array, then scale all vertex positions by `scale`. Mirrors
  `greedy_mesh_reduced`."
  [data size palette scale]
  (let [idx3 (fn [x y z] (+ (* y size size) (* z size) x))]
    (->voxel-mesh
     (reduce
      (fn [acc axis]
        (let [[u-axis v-axis] (case axis 0 [1 2] 1 [0 2] [0 1])]
          (reduce
           (fn [acc positive?]
             (reduce
              (fn [acc d]
                (let [mask (vec (repeat size (vec (repeat size :air))))
                      mask (reduce
                            (fn [mask [v u]]
                              (let [[x y z] (pos3 axis d u-axis u v-axis v)
                                    block (block-from-index (nth data (idx3 x y z)))]
                                (if-not (solid? block)
                                  mask
                                  (let [nd (if positive? (inc d) (dec d))
                                        neighbor (if (and (>= nd 0) (< nd size))
                                                   (let [[nx ny nz] (pos3 axis nd u-axis u v-axis v)]
                                                     (block-from-index (nth data (idx3 nx ny nz))))
                                                   :air)]
                                    (if (or (not (solid? neighbor)) (transparent? neighbor))
                                      (assoc-in mask [v u] block)
                                      mask)))))
                            mask
                            (for [v (range size) u (range size)] [v u]))
                      visited (vec (repeat size (vec (repeat size false))))]
                  (loop [acc acc, visited visited, v 0, u 0]
                    (cond
                      (>= v size) acc
                      (>= u size) (recur acc visited (inc v) 0)
                      (or (get-in visited [v u]) (= (get-in mask [v u]) :air))
                      (recur acc visited v (inc u))
                      :else
                      (let [block (get-in mask [v u])
                            w (loop [w 1]
                                (if (and (< (+ u w) size)
                                         (= (get-in mask [v (+ u w)]) block)
                                         (not (get-in visited [v (+ u w)])))
                                  (recur (inc w))
                                  w))
                            h (loop [h 1]
                                (if (and (< (+ v h) size)
                                         (every? (fn [du] (and (= (get-in mask [(+ v h) (+ u du)]) block)
                                                                (not (get-in visited [(+ v h) (+ u du)]))))
                                                 (range w)))
                                  (recur (inc h))
                                  h))
                            visited' (reduce (fn [vis dv]
                                                (reduce (fn [vis du] (assoc-in vis [(+ v dv) (+ u du)] true))
                                                        vis (range w)))
                                              visited (range h))
                            color (get palette (get block-index block) [1.0 1.0 1.0 1.0])
                            face (axis-face axis positive?)
                            origin (-> (vec (repeat 3 0.0))
                                       (assoc axis (* scale (double (if positive? (inc d) d))))
                                       (assoc u-axis (* scale (double u)))
                                       (assoc v-axis (* scale (double v))))
                            du-vec (assoc (vec (repeat 3 0.0)) u-axis (* scale (double w)))
                            dv-vec (assoc (vec (repeat 3 0.0)) v-axis (* scale (double h)))
                            acc' (emit-quad acc origin du-vec dv-vec (face-normal face) color positive?)]
                        (recur acc' visited' v (+ u w)))))))
              acc (range size)))
           acc [true false])))
      [[] []]
      (range 3)))))

(defn- single-cube-mesh
  "Generate a single-cube mesh (LOD 3) with the dominant color from the
  chunk. Mirrors `single_cube_mesh`."
  [chunk palette]
  (let [counts (reduce
                (fn [counts [x y z]]
                  (let [b (chunk-get chunk x y z)]
                    (if (solid? b)
                      (update counts (get block-index b) (fnil inc 0))
                      counts)))
                {}
                (for [y (range chunk-size) z (range chunk-size) x (range chunk-size)] [x y z]))
        [best best-count] (reduce (fn [[best-i best-c] i]
                                     (let [c (get counts i 0)]
                                       (if (> c best-c) [i c] [best-i best-c])))
                                   [0 0] (range 16))]
    (if (zero? best-count)
      {:vertices [] :indices [] :vertex-count 0 :index-count 0}
      (let [color (get palette best [1.0 1.0 1.0 1.0])
            s (double chunk-size)
            faces [[:pos-x [s 0.0 0.0] [0.0 0.0 s] [0.0 s 0.0]]
                   [:neg-x [0.0 0.0 s] [0.0 0.0 (- s)] [0.0 s 0.0]]
                   [:pos-y [0.0 s 0.0] [s 0.0 0.0] [0.0 0.0 s]]
                   [:neg-y [0.0 0.0 s] [s 0.0 0.0] [0.0 0.0 (- s)]]
                   [:pos-z [0.0 0.0 s] [s 0.0 0.0] [0.0 s 0.0]]
                   [:neg-z [s 0.0 0.0] [(- s) 0.0 0.0] [0.0 s 0.0]]]]
        (->voxel-mesh
         (reduce (fn [acc [face origin du dv]]
                   (emit-quad acc origin du dv (face-normal face) color
                              (contains? #{:pos-x :pos-y :pos-z} face)))
                 [[] []] faces))))))

(defn lod-mesh
  "Level-of-detail mesh generation for voxel chunks.
  - LOD 0: full greedy mesh (delegates to `greedy-mesh`).
  - LOD 1: down-sample 2x2x2 blocks via majority-vote, greedy mesh at half
    resolution, scale x2.
  - LOD 2: down-sample 4x4x4, greedy mesh at quarter resolution, scale x4.
  - LOD 3: single cube with dominant color (24 vertices).
  Mirrors `lod_mesh`."
  [chunk palette lod-level]
  (case lod-level
    0 (greedy-mesh chunk palette)
    1 (let [[data size] (downsample-majority chunk 2)]
        (greedy-mesh-reduced data size palette 2.0))
    2 (let [[data size] (downsample-majority chunk 4)]
        (greedy-mesh-reduced data size palette 4.0))
    (single-cube-mesh chunk palette)))
