(ns voxel
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-voxel Rust crate
  (kotoba-lang/kami-engine, deleted in PR #82 \"Remove Rust workspace from kami-engine\")
  as part of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Original `kami-voxel/src/lib.rs` (410 lines) defined a `Voxel` value type plus a
  `Volume` trait implemented by three storage backends — `DenseVolume` (flat W*H*D
  array), `SparseVolume` (hashmap of only-filled cells), `OctreeVolume` (adaptive
  power-of-2 sparse tree) — and a `VoxelVolume` enum wrapper that dispatches across
  them. Here every backend is a plain CLJC map tagged with `:type`, and the trait
  methods become generic functions (`vol-get`/`vol-set`/...) that `case`-dispatch on
  `:type` — this collapses the Rust trait + enum-wrapper duplication into one thing,
  since CLJC data is already open and taggable. Pure data + pure functions throughout;
  no IO/GPU (native execution stays substrate, per the migration ADR).")

;; ---------------------------------------------------------------------------
;; Voxel — single voxel value (Rust `struct Voxel { material: u8, color: [f32;4] }`)
;; ---------------------------------------------------------------------------

(defn air
  "The empty/default voxel (material 0, transparent black color).
  Mirrors Rust `Voxel::default()` / `Voxel::air()`."
  []
  {:material 0 :color [0.0 0.0 0.0 0.0]})

(defn solid?
  "A voxel is solid iff its material is non-zero. Mirrors `Voxel::is_solid`."
  [voxel]
  (pos? (:material voxel)))

;; ---------------------------------------------------------------------------
;; Dense volume — flat W*H*D vector, row-major (x + y*w + z*w*h), like the
;; original's `data[(z * h * w + y * w + x) as usize]` indexing.
;; ---------------------------------------------------------------------------

(defn- dense-index [w h x y z]
  (+ (* z h w) (* y w) x))

(defn- in-bounds? [w h d x y z]
  (and (>= x 0) (>= y 0) (>= z 0) (< x w) (< y h) (< z d)))

(defn dense-new
  "New dense volume of size w*h*d, all cells air. Mirrors `DenseVolume::new`."
  [w h d]
  {:type :dense :w w :h h :d d :data (vec (repeat (* w h d) (air)))})

(defn- dense-get [vol x y z]
  (let [{:keys [w h d data]} vol]
    (if (in-bounds? w h d x y z)
      (nth data (dense-index w h x y z))
      (air))))

(defn- dense-set [vol x y z voxel]
  (let [{:keys [w h d data]} vol]
    (if (in-bounds? w h d x y z)
      (assoc vol :data (assoc data (dense-index w h x y z) voxel))
      vol)))

(defn- dense-count-filled [vol]
  (count (filter solid? (:data vol))))

;; ---------------------------------------------------------------------------
;; Sparse volume — map keyed by [x y z], storing only non-air voxels.
;; Mirrors `SparseVolume` (HashMap<u64, Voxel> with a packed key); a `[x y z]`
;; vector key is the portable CLJC equivalent of the Rust bit-packed u64 key.
;; ---------------------------------------------------------------------------

(defn sparse-new
  "New sparse volume of logical size w*h*d, initially empty. Mirrors `SparseVolume::new`."
  [w h d]
  {:type :sparse :w w :h h :d d :map {}})

(defn- sparse-get [vol x y z]
  (get (:map vol) [x y z] (air)))

(defn- sparse-set [vol x y z voxel]
  (if (solid? voxel)
    (update vol :map assoc [x y z] voxel)
    (update vol :map dissoc [x y z])))

(defn- sparse-count-filled [vol]
  (count (:map vol)))

(defn filled-iter
  "Iterate only over filled voxels of a sparse volume as `[x y z voxel]` tuples.
  Sparse-specific optimization, mirrors `SparseVolume::filled_iter`."
  [vol]
  (map (fn [[[x y z] v]] [x y z v]) (:map vol)))

;; ---------------------------------------------------------------------------
;; Octree volume — adaptive resolution, power-of-2 size. A node is one of:
;;   :empty              — Rust `OctreeNode::Empty`
;;   [:leaf voxel]        — Rust `OctreeNode::Leaf(Voxel)`
;;   [:branch [8 nodes]]  — Rust `OctreeNode::Branch(Box<[OctreeNode; 8]>)`
;; ---------------------------------------------------------------------------

(defn- power-of-two? [n]
  (and (pos? n) (zero? (bit-and n (dec n)))))

(defn octree-new
  "New octree volume of the given power-of-2 size, initially fully empty.
  Mirrors `OctreeVolume::new` (asserts size is a power of two)."
  [size]
  (assert (power-of-two? size) "octree size must be power of 2")
  {:type :octree :size size :root :empty})

(defn- octant-index [x y z half]
  (bit-or (if (>= x half) 1 0)
          (bit-shift-left (if (>= y half) 1 0) 1)
          (bit-shift-left (if (>= z half) 1 0) 2)))

(defn- octree-insert-node [node x y z size v]
  (if (= size 1)
    [:leaf v]
    (let [half (quot size 2)
          idx (octant-index x y z half)
          x' (mod x half) y' (mod y half) z' (mod z half)
          children (cond
                     (= node :empty)
                     (vec (repeat 8 :empty))

                     (and (vector? node) (= (first node) :leaf))
                     (vec (repeat 8 node))

                     (and (vector? node) (= (first node) :branch))
                     (second node)

                     :else (vec (repeat 8 :empty)))
          child (nth children idx)
          children' (assoc children idx (octree-insert-node child x' y' z' half v))]
      [:branch children'])))

(defn- octree-query-node [node x y z size]
  (cond
    (= node :empty) (air)
    (and (vector? node) (= (first node) :leaf)) (second node)
    (and (vector? node) (= (first node) :branch))
    (let [half (quot size 2)]
      (if (zero? half)
        (air)
        (let [idx (octant-index x y z half)
              children (second node)]
          (octree-query-node (nth children idx) (mod x half) (mod y half) (mod z half) half))))
    :else (air)))

(defn- octree-in-bounds? [size x y z]
  (and (>= x 0) (>= y 0) (>= z 0) (< x size) (< y size) (< z size)))

(defn- octree-get [vol x y z]
  (if (octree-in-bounds? (:size vol) x y z)
    (octree-query-node (:root vol) x y z (:size vol))
    (air)))

(defn- octree-set [vol x y z voxel]
  (if (octree-in-bounds? (:size vol) x y z)
    (update vol :root octree-insert-node x y z (:size vol) voxel)
    vol))

(defn- octree-count-filled [vol]
  (let [size (:size vol)]
    (reduce
     (fn [c [x y z]]
       (if (solid? (octree-get vol x y z)) (inc c) c))
     0
     (for [z (range size) y (range size) x (range size)] [x y z]))))

;; ---------------------------------------------------------------------------
;; Volume — generic trait-equivalent functions, dispatch on `:type`.
;; Mirrors the Rust `trait Volume` (implemented by all three backends) plus
;; the `VoxelVolume` enum wrapper — in CLJC these collapse into one dispatch.
;; ---------------------------------------------------------------------------

(def volume-types
  "Valid `:type` tags for a volume map."
  #{:dense :sparse :octree})

(defn vol-width [vol]
  (case (:type vol)
    :octree (:size vol)
    (:w vol)))

(defn vol-height [vol]
  (case (:type vol)
    :octree (:size vol)
    (:h vol)))

(defn vol-depth [vol]
  (case (:type vol)
    :octree (:size vol)
    (:d vol)))

(defn vol-get
  "Read the voxel at (x,y,z), returning `air` if out of bounds / unset.
  Mirrors `Volume::get`."
  [vol x y z]
  (case (:type vol)
    :dense (dense-get vol x y z)
    :sparse (sparse-get vol x y z)
    :octree (octree-get vol x y z)))

(defn vol-set
  "Return a new volume with (x,y,z) set to `voxel`. Mirrors `Volume::set`
  (functional: CLJC data is immutable, so this returns rather than mutates)."
  [vol x y z voxel]
  (case (:type vol)
    :dense (dense-set vol x y z voxel)
    :sparse (sparse-set vol x y z voxel)
    :octree (octree-set vol x y z voxel)))

(defn vol-count-filled
  "Count of solid voxels in the volume. Mirrors `Volume::count_filled`."
  [vol]
  (case (:type vol)
    :dense (dense-count-filled vol)
    :sparse (sparse-count-filled vol)
    :octree (octree-count-filled vol)))

;; ---------------------------------------------------------------------------
;; VoxelVolume wrapper equivalents — since backends already share the same
;; tagged-map shape and generic `vol-*` dispatch, the Rust `VoxelVolume` enum
;; wrapper's constructors/conversion/introspection are these thin aliases.
;; ---------------------------------------------------------------------------

(defn new-dense
  "Mirrors `VoxelVolume::new_dense`."
  [w h d]
  (dense-new w h d))

(defn new-sparse
  "Mirrors `VoxelVolume::new_sparse`."
  [w h d]
  (sparse-new w h d))

(defn new-octree
  "Mirrors `VoxelVolume::new_octree`."
  [size]
  (octree-new size))

(defn to-sparse
  "Convert any volume to an equivalent sparse volume, copying only solid
  voxels. Mirrors `VoxelVolume::to_sparse`."
  [vol]
  (let [w (vol-width vol) h (vol-height vol) d (vol-depth vol)]
    (reduce
     (fn [s [x y z]]
       (let [v (vol-get vol x y z)]
         (if (solid? v)
           (vol-set s x y z v)
           s)))
     (sparse-new w h d)
     (for [z (range d) y (range h) x (range w)] [x y z]))))

(defn storage-type
  "The backend's storage type as a string (\"dense\"/\"sparse\"/\"octree\").
  Mirrors `VoxelVolume::storage_type`."
  [vol]
  (name (:type vol)))
