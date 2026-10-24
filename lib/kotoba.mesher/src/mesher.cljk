(ns mesher
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-mesher Rust
  crate (`kami-mesher/src/lib.rs`, `kotoba-lang/kami-engine`, deleted in PR #82
  \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl migration
  (ADR-2607010930, `com-junkawasaki/root`). This is a plain-CLJC interim
  implementation standing in for logic the migration ledger originally
  classified `:port-to-WGSL-compute` — per owner decision it is ported here
  as pure portable data + functions (no GPU/WGSL, no IO) rather than an
  actual WGSL compute shader.

  Purpose: Marching Cubes isosurface mesh generation from a scalar density
  (signed-distance) field sampled on a regular grid, using the standard
  Paul Bourke / Lorensen-Cline edge/triangle lookup tables (`mesher.mc-tables`),
  plus a simple face-culling mesher over a dense voxel volume (legacy name
  `marching-cubes` kept for parity with the original Rust API even though it
  is actually a Minecraft-style block face mesher, not true marching cubes).

  All original Rust types (`LoadedMesh`, `Voxel`, `VoxelVolume`) are ported
  as plain CLJC maps with keyword keys:
    - a *mesh* is `{:vertex-count int :index-count int :vertices [floats,
      interleaved pos3+norm3+uv2 per vertex] :indices [ints]}`
    - a *voxel* is `{:material int :color [r g b a]}` (or `nil` for empty)
    - a *voxel volume* is `{:width int :height int :depth int :cells [voxel...]}`
      (dense, row-major x-fastest — the original crate's sparse/octree voxel
      volume variants live in the separate, still-Rust `kami-voxel` crate and
      are out of scope for this restoration; see README)."
  (:require [mesher.mc-tables :as mct]))

;; ---------------------------------------------------------------------------
;; Portable math helpers (#?(:clj ...) / #?(:cljs ...) reader conditionals so
;; this namespace runs unmodified on the JVM and in ClojureScript).
;; ---------------------------------------------------------------------------

(defn- sqrt* [x]
  #?(:clj  (Math/sqrt (double x))
     :cljs (js/Math.sqrt x)))

(defn- abs* [x]
  #?(:clj  (Math/abs (double x))
     :cljs (js/Math.abs x)))

(defn- round* [x]
  #?(:clj  (Math/round (double x))
     :cljs (js/Math.round x)))

(defn- clamp01 [x]
  (max 0.0 (min 1.0 (double x))))

;; ---------------------------------------------------------------------------
;; Vertex-buffer helpers
;; ---------------------------------------------------------------------------

(defn- interleave-verts
  "positions/normals: flat [x y z x y z ...] triples; uvs: flat [u v u v ...]
  pairs, all index-aligned per vertex. Returns a flat interleaved
  pos3+norm3+uv2 (stride 8) vertex buffer, matching the original
  `kami_render::mesh::interleave` layout."
  [positions normals uvs]
  (let [n (quot (count positions) 3)]
    (vec (mapcat (fn [i]
                   (let [pi (* i 3) ui (* i 2)]
                     (concat (subvec positions pi (+ pi 3))
                             (subvec normals pi (+ pi 3))
                             (subvec uvs ui (+ ui 2)))))
                 (range n)))))

;; ---------------------------------------------------------------------------
;; SDF (scalar density field) -> mesh via Marching Cubes
;; ---------------------------------------------------------------------------

(def ^:private corner-offsets
  "Corner positions (as unit-cube offsets) for a Marching Cubes cell at
  (cx, cy, cz), in the standard 0-7 corner numbering."
  [[0 0 0] [1 0 0] [1 1 0] [0 1 0]
   [0 0 1] [1 0 1] [1 1 1] [0 1 1]])

(defn edge-hash
  "Unique hash for an edge in the grid (for vertex de-duplication across
  adjacent cells). `sample` is a `(fn [x y z] -> [dist [r g b a]])`."
  [cx cy cz edge res]
  (let [[a b] (nth mct/edge-vertices edge)
        [oax oay oaz] (nth corner-offsets a)
        [obx oby obz] (nth corner-offsets b)
        ax (+ cx oax) ay (+ cy oay) az (+ cz oaz)
        bx (+ cx obx) by (+ cy oby) bz (+ cz obz)
        a-first? (<= (compare [az ay ax] [bz by bx]) 0)
        [[p0x p0y p0z] [p1x p1y p1z]] (if a-first?
                                        [[ax ay az] [bx by bz]]
                                        [[bx by bz] [ax ay az]])
        r1 (inc res)
        encode (fn [x y z] (+ (* z r1 r1) (* y r1) x))]
    (+ (* (encode p0x p0y p0z) (* r1 r1 r1))
       (encode p1x p1y p1z))))

(defn- process-cell
  "Marching Cubes for a single grid cell (cx,cy,cz); folds vertex/index/color
  output into `state` (a map of :positions :normals :uvs :colors :indices
  :edge-map, all growing vectors except :edge-map which is a map from
  edge-hash -> vertex index used to de-duplicate shared edge vertices)."
  [state sample origin step res eps cx cy cz]
  (let [corner-pos (mapv (fn [[ox oy oz]]
                            [(+ origin (* (+ cx ox) step))
                             (+ origin (* (+ cy oy) step))
                             (+ origin (* (+ cz oz) step))])
                          corner-offsets)
        samples (mapv (fn [[px py pz]] (sample px py pz)) corner-pos)
        dists (mapv first samples)
        colors (mapv second samples)
        cube-idx (reduce (fn [acc i]
                            (if (<= (nth dists i) 0.0)
                              (bit-or acc (bit-shift-left 1 i))
                              acc))
                          0 (range 8))
        edge-bits (nth mct/edge-table cube-idx)]
    (if (zero? edge-bits)
      state
      (let [[state edge-verts]
            (reduce
             (fn [[state edge-verts] e]
               (if (zero? (bit-and edge-bits (bit-shift-left 1 e)))
                 [state edge-verts]
                 (let [[a b] (nth mct/edge-vertices e)
                       ekey (edge-hash cx cy cz e res)]
                   (if-let [existing (get (:edge-map state) ekey)]
                     [state (assoc edge-verts e existing)]
                     (let [da (nth dists a) db (nth dists b)
                           t (if (> (abs* (- da db)) 1e-6)
                               (/ da (- da db))
                               0.5)
                           t (clamp01 t)
                           [ax ay az] (nth corner-pos a)
                           [bx by bz] (nth corner-pos b)
                           vx (+ ax (* t (- bx ax)))
                           vy (+ ay (* t (- by ay)))
                           vz (+ az (* t (- bz az)))
                           ca (nth colors a) cb (nth colors b)
                           vc [(+ (nth ca 0) (* t (- (nth cb 0) (nth ca 0))))
                               (+ (nth ca 1) (* t (- (nth cb 1) (nth ca 1))))
                               (+ (nth ca 2) (* t (- (nth cb 2) (nth ca 2))))
                               (+ (nth ca 3) (* t (- (nth cb 3) (nth ca 3))))]
                           dx (- (first (sample (+ vx eps) vy vz)) (first (sample (- vx eps) vy vz)))
                           dy (- (first (sample vx (+ vy eps) vz)) (first (sample vx (- vy eps) vz)))
                           dz (- (first (sample vx vy (+ vz eps))) (first (sample vx vy (- vz eps))))
                           len (max (sqrt* (+ (* dx dx) (* dy dy) (* dz dz))) 1e-6)
                           idx (quot (count (:positions state)) 3)
                           state (-> state
                                     (update :positions into [vx vy vz])
                                     (update :normals into [(/ dx len) (/ dy len) (/ dz len)])
                                     (update :uvs into [0.0 0.0])
                                     (update :colors conj vc)
                                     (assoc-in [:edge-map ekey] idx))]
                       [state (assoc edge-verts e idx)])))))
             [state (vec (repeat 12 nil))]
             (range 12))
            tri-row (nth mct/tri-table cube-idx)]
        (reduce
         (fn [state i]
           (let [e0 (nth tri-row i)]
             (if (neg? e0)
               (reduced state)
               (let [e1 (nth tri-row (+ i 1)) e2 (nth tri-row (+ i 2))
                     v0 (nth edge-verts e0) v1 (nth edge-verts e1) v2 (nth edge-verts e2)]
                 (if (and v0 v1 v2)
                   (update state :indices into [v0 v1 v2])
                   state)))))
         state
         (range 0 16 3))))))

(defn sdf-to-colored-mesh
  "SDF -> mesh with per-vertex colors. `sample` is
  `(fn [x y z] -> [dist [r g b a]])`. `resolution` is the per-axis cell count;
  `bounds` is the half-extent of the sampled cube (grid spans
  [-bounds, +bounds] on each axis).

  Returns `[mesh vertex-colors]` where `vertex-colors[i]` is the RGBA color
  of mesh vertex `i`."
  [sample resolution bounds]
  (let [res (long resolution)
        step (/ (* bounds 2.0) res)
        origin (- bounds)
        eps (* step 0.05)
        cells (for [cz (range res) cy (range res) cx (range res)] [cx cy cz])
        init {:positions [] :normals [] :uvs [] :colors [] :indices [] :edge-map {}}
        state (reduce (fn [state [cx cy cz]]
                         (process-cell state sample origin step res eps cx cy cz))
                       init cells)
        vertices (interleave-verts (:positions state) (:normals state) (:uvs state))
        mesh {:vertex-count (quot (count (:positions state)) 3)
              :index-count (count (:indices state))
              :vertices vertices
              :indices (:indices state)}]
    [mesh (:colors state)]))

(defn sdf-to-mesh
  "Proper Marching Cubes with Paul Bourke lookup tables. `sample` is
  `(fn [x y z] -> [dist [r g b a]])` (the color is ignored here; use
  `sdf-to-colored-mesh` to keep it)."
  [sample resolution bounds]
  (first (sdf-to-colored-mesh sample resolution bounds)))

(defn split-mesh-by-color
  "Split a colored mesh into sub-meshes grouped by quantized color. Each
  group becomes a separate mesh with a uniform (average) color. Returns a
  vector of `[mesh color]`. Color is quantized to 3 bits/channel (8 levels)
  so SmoothUnion-style boundary blends merge into their nearest distinct
  color group."
  [mesh vertex-colors]
  (if (or (zero? (:index-count mesh)) (empty? vertex-colors))
    []
    (let [quantize (fn [[r g b _a]]
                      (let [rq (long (round* (* r 7.0)))
                            gq (long (round* (* g 7.0)))
                            bq (long (round* (* b 7.0)))]
                        (bit-or (bit-shift-left rq 6) (bit-shift-left gq 3) bq)))
          indices (:indices mesh)
          tri-count (quot (:index-count mesh) 3)
          groups (reduce
                  (fn [groups tri]
                    (let [i0 (nth indices (* tri 3))
                          i1 (nth indices (+ (* tri 3) 1))
                          i2 (nth indices (+ (* tri 3) 2))
                          c0 (nth vertex-colors i0)
                          c1 (nth vertex-colors i1)
                          c2 (nth vertex-colors i2)
                          c [(/ (+ (nth c0 0) (nth c1 0) (nth c2 0)) 3.0)
                             (/ (+ (nth c0 1) (nth c1 1) (nth c2 1)) 3.0)
                             (/ (+ (nth c0 2) (nth c1 2) (nth c2 2)) 3.0)
                             1.0]
                          k (quantize c)]
                      (update groups k
                              (fn [entry]
                                (if entry
                                  (update entry :tris conj tri)
                                  {:tris [tri] :color c})))))
                  {} (range tri-count))
          stride 8
          vertices (:vertices mesh)]
      (mapv
       (fn [[_k {:keys [tris color]}]]
         (let [acc (reduce
                    (fn [acc tri]
                      (reduce
                       (fn [acc k]
                         (let [old-idx (nth indices (+ (* tri 3) k))]
                           (if-let [ni (get (:remap acc) old-idx)]
                             (update acc :idxs conj ni)
                             (let [ni (quot (count (:verts acc)) stride)
                                   base (* old-idx stride)]
                               (-> acc
                                   (update :verts into (subvec vertices base (+ base stride)))
                                   (update :idxs conj ni)
                                   (assoc-in [:remap old-idx] ni))))))
                       acc (range 3)))
                    {:verts [] :idxs [] :remap {}} tris)]
           [{:vertex-count (quot (count (:verts acc)) stride)
             :index-count (count (:idxs acc))
             :vertices (:verts acc)
             :indices (:idxs acc)}
            color]))
       groups))))

;; ---------------------------------------------------------------------------
;; Dense voxel volume + face-culling mesher
;;
;; The original crate's `VoxelVolume` (dense/sparse/octree variants, from the
;; separate `kami-voxel` crate) is out of scope for this restoration — this
;; provides only the minimal dense representation needed by `marching-cubes`
;; below and by its tests.
;; ---------------------------------------------------------------------------

(defn make-dense-volume
  "A dense, row-major (x-fastest) voxel grid: `{:width w :height h :depth d
  :cells [voxel-or-nil ...]}`."
  [w h d]
  {:width w :height h :depth d :cells (vec (repeat (* (long w) (long h) (long d)) nil))})

(defn- volume-index [{:keys [width height]} x y z]
  (+ x (* y width) (* z width height)))

(defn set-voxel
  "Returns a new volume with the voxel at (x,y,z) set to `voxel`
  (a `{:material int :color [r g b a]}` map)."
  [volume x y z voxel]
  (assoc-in volume [:cells (volume-index volume x y z)] voxel))

(defn get-voxel
  "Voxel at (x,y,z), or `nil` if empty / out of range."
  [{:keys [width height depth] :as volume} x y z]
  (when (and (<= 0 x) (< x width) (<= 0 y) (< y height) (<= 0 z) (< z depth))
    (nth (:cells volume) (volume-index volume x y z))))

(defn solid?
  "A voxel is solid iff it is present and its material is non-zero
  (mirrors the original `Voxel::is_solid`)."
  [voxel]
  (and (some? voxel) (not= 0 (:material voxel))))

(def ^:private face-defs
  "[dx dy dz normal] for each of the 6 cube faces."
  [[1 0 0 [1.0 0.0 0.0]]
   [-1 0 0 [-1.0 0.0 0.0]]
   [0 1 0 [0.0 1.0 0.0]]
   [0 -1 0 [0.0 -1.0 0.0]]
   [0 0 1 [0.0 0.0 1.0]]
   [0 0 -1 [0.0 0.0 -1.0]]])

(defn- face-verts
  "The 4 CCW corner positions of a unit cube face at `pos` (cube min-corner)
  with side length `scale`, for the face whose outward normal is `normal`."
  [pos normal scale]
  (let [hs (* scale 0.5)
        [px py pz] (mapv + pos [hs hs hs])]
    (case normal
      [1.0 0.0 0.0]  [[(+ px hs) (- py hs) (- pz hs)]
                       [(+ px hs) (+ py hs) (- pz hs)]
                       [(+ px hs) (+ py hs) (+ pz hs)]
                       [(+ px hs) (- py hs) (+ pz hs)]]
      [-1.0 0.0 0.0] [[(- px hs) (- py hs) (+ pz hs)]
                       [(- px hs) (+ py hs) (+ pz hs)]
                       [(- px hs) (+ py hs) (- pz hs)]
                       [(- px hs) (- py hs) (- pz hs)]]
      [0.0 1.0 0.0]  [[(- px hs) (+ py hs) (- pz hs)]
                       [(+ px hs) (+ py hs) (- pz hs)]
                       [(+ px hs) (+ py hs) (+ pz hs)]
                       [(- px hs) (+ py hs) (+ pz hs)]]
      [0.0 -1.0 0.0] [[(- px hs) (- py hs) (+ pz hs)]
                       [(+ px hs) (- py hs) (+ pz hs)]
                       [(+ px hs) (- py hs) (- pz hs)]
                       [(- px hs) (- py hs) (- pz hs)]]
      [0.0 0.0 1.0]  [[(- px hs) (- py hs) (+ pz hs)]
                       [(- px hs) (+ py hs) (+ pz hs)]
                       [(+ px hs) (+ py hs) (+ pz hs)]
                       [(+ px hs) (- py hs) (+ pz hs)]]
      ;; [0.0 0.0 -1.0]
      [[(+ px hs) (- py hs) (- pz hs)]
       [(+ px hs) (+ py hs) (- pz hs)]
       [(- px hs) (+ py hs) (- pz hs)]
       [(- px hs) (- py hs) (- pz hs)]])))

(defn marching-cubes
  "VoxelVolume face-based mesher (Minecraft-style blocks): emits one quad per
  exposed (solid, with a non-solid or out-of-bounds neighbor) cube face.
  Name kept for parity with the original Rust API, even though this is a
  face-culling block mesher rather than true Marching Cubes (see
  `sdf-to-mesh` for the isosurface algorithm)."
  [volume scale]
  (let [{:keys [width height depth]} volume
        offset [(/ (* (- width) scale) 2.0)
                (/ (* (- height) scale) 2.0)
                (/ (* (- depth) scale) 2.0)]
        cells (for [z (range depth) y (range height) x (range width)] [x y z])
        state (reduce
               (fn [state [x y z]]
                 (if-not (solid? (get-voxel volume x y z))
                   state
                   (let [pos (mapv + (mapv * [x y z] [scale scale scale]) offset)]
                     (reduce
                      (fn [state [dx dy dz normal]]
                        (let [nx (+ x dx) ny (+ y dy) nz (+ z dz)]
                          (if (solid? (get-voxel volume nx ny nz))
                            state
                            (let [base (quot (count (:positions state)) 3)
                                  [v0 v1 v2 v3] (face-verts pos normal scale)]
                              (-> state
                                  (update :positions into (mapcat identity [v0 v1 v2 v3]))
                                  (update :normals into (mapcat identity (repeat 4 normal)))
                                  (update :uvs into (mapcat identity (repeat 4 [0.0 0.0])))
                                  (update :indices into [base (+ base 1) (+ base 2)
                                                          base (+ base 2) (+ base 3)]))))))
                      state
                      face-defs)))
                 )
               {:positions [] :normals [] :uvs [] :indices []}
               cells)
        vertices (interleave-verts (:positions state) (:normals state) (:uvs state))]
    {:vertex-count (quot (count (:positions state)) 3)
     :index-count (count (:indices state))
     :vertices vertices
     :indices (:indices state)}))

(defn greedy-mesh-volume
  "Alias kept for parity with the original crate; currently delegates to
  `marching-cubes` (the original Rust also had `greedy_mesh_volume` as a
  straight delegate, not an actual greedy-meshing implementation)."
  [volume scale]
  (marching-cubes volume scale))
