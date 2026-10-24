(ns voxel.vdb
  "The VDB tree: a sparse voxel hierarchy with fixed branching and tiles, in
  the shape OpenVDB's `Tree4<T, 5, 4, 3>` uses.

  A dense grid pays for every voxel; an octree pays a comparison per level.
  VDB's answer is a shallow tree with wide, FIXED branching — 8^3 voxels in a
  leaf, 16^3 leaves in an internal node, 32^3 of those above — so a coordinate
  maps to a slot by shifting and masking rather than by descending a tree.
  `voxel/sparse-new` is a hash map of filled cells, which is sparse but has
  neither the locality nor the tiles; this is the structure the format is
  named after.

  What that buys, and what is measured: the active voxel count and the active
  bounding box come off the tree without visiting empty space; topology union,
  intersection and difference are set operations on active voxels; and a node
  whose children are all present and equal collapses to a TILE, so a filled
  region costs one entry rather than 512.

  **This is the data structure, not the file format.** `.vdb` and `.nvdb` are
  neither read nor written here. The NanoVDB magic numbers below were confirmed
  from the upstream header on 2026-08-23 and are recorded as a starting point,
  but the byte layout of `FileHeader` (16 bytes) and `FileMetaData` (176 bytes)
  could not be obtained without guessing — and a parser written by guessing
  round-trips with itself while opening nobody else's file. `to-edn` and
  `from-edn` are the serialisation that exists, and they say in their own error
  message that they are this library's own format.

  Not here: values other than scalars, levels beyond the three, narrow-band
  level-set operations, Blosc or ZIP compression, and delayed loading."
  (:require [kotoba.lang.text :as string]))

(def nanovdb-magic
  "Confirmed from AcademySoftwareFoundation/openvdb nanovdb/NanoVDB.h,
  2026-08-23. Recorded, NOT acted on — see the namespace docstring."
  {:numb 0x304244566f6e614e   ; "NanoVDB0"
   :grid 0x314244566f6e614e   ; "NanoVDB1"
   :file 0x324244566f6e614e}) ; "NanoVDB2"

(def leaf-log2 3)
(def internal-log2 4)
(def upper-log2 5)

(def leaf-dim (bit-shift-left 1 leaf-log2))          ; 8
(def internal-dim (bit-shift-left 1 internal-log2))  ; 16
(def upper-dim (bit-shift-left 1 upper-log2))        ; 32

(def leaf-span leaf-dim)                             ; 8
(def internal-span (* internal-dim leaf-span))       ; 128
(def upper-span (* upper-dim internal-span))         ; 4096

(defn grid
  ([] (grid 0))
  ([background] {:vdb/background background :vdb/root {}}))

(defn- floor-div [a b] (let [q (quot a b) r (rem a b)] (if (and (neg? r) (not (zero? r))) (dec q) q)))
(defn- pos-mod [a b] (let [m (rem a b)] (if (neg? m) (+ m b) m)))

(defn- root-key [c] (mapv #(floor-div % upper-span) c))
(defn- local [c] (mapv #(pos-mod % upper-span) c))
(defn- upper-index [l] (mapv #(quot % internal-span) l))
(defn- internal-index [l] (mapv #(quot (pos-mod % internal-span) leaf-span) l))
(defn- leaf-index [l] (mapv #(pos-mod % leaf-span) l))

(defn- tile? [n] (and (map? n) (contains? n :tile)))

(defn get-voxel
  [{:vdb/keys [background root]} coord]
  (let [l (local coord)]
    (loop [node (get root (root-key coord))
           idx [upper-index internal-index leaf-index]]
      (cond
        (nil? node) background
        (tile? node) (:tile node)
        (empty? idx) node
        :else (recur (get node ((first idx) l)) (rest idx))))))

(defn- expand-tile
  "A tile written into becomes an explicit map of its own value first. Without
  this the write would silently change every voxel under the tile — the exact
  failure a tile representation invites."
  [node dim]
  (if (tile? node)
    (into {} (for [a (range dim) b (range dim) c (range dim)] [[a b c] (:tile node)]))
    (or node {})))

(defn set-voxel
  [{:vdb/keys [background] :as g} coord value]
  (let [rk (root-key coord) l (local coord)
        ui (upper-index l) ii (internal-index l) li (leaf-index l)]
    (update-in g [:vdb/root rk]
               (fn [upper]
                 (let [upper (expand-tile upper upper-dim)
                       internal (expand-tile (get upper ui) internal-dim)
                       leaf (expand-tile (get internal ii) leaf-dim)
                       leaf (if (= value background) (dissoc leaf li) (assoc leaf li value))
                       internal (if (empty? leaf) (dissoc internal ii) (assoc internal ii leaf))
                       upper (if (empty? internal) (dissoc upper ui) (assoc upper ui internal))]
                   (when (seq upper) upper))))))

(defn- node-voxels [node origin span]
  (cond
    (nil? node) []
    (tile? node) (for [x (range span) y (range span) z (range span)]
                   [(mapv + origin [x y z]) (:tile node)])
    (= span leaf-span) (map (fn [[idx v]] [(mapv + origin idx) v]) node)
    :else
    (let [dim (if (= span upper-span) upper-dim internal-dim)
          child-span (quot span dim)]
      (mapcat (fn [[idx child]]
                (node-voxels child (mapv + origin (mapv #(* % child-span) idx)) child-span))
              node))))

(defn active-voxels
  [{:vdb/keys [root]}]
  (mapcat (fn [[rk upper]] (node-voxels upper (mapv #(* % upper-span) rk) upper-span)) root))

(defn active-count [g] (count (active-voxels g)))

(defn bounds
  [g]
  (let [cs (map first (active-voxels g))]
    (when (seq cs)
      [(mapv (fn [i] (apply min (map #(nth % i) cs))) [0 1 2])
       (mapv (fn [i] (apply max (map #(nth % i) cs))) [0 1 2])])))

(defn fill
  [g lo hi value]
  (reduce (fn [acc c] (set-voxel acc c value)) g
          (for [x (range (nth lo 0) (inc (nth hi 0)))
                y (range (nth lo 1) (inc (nth hi 1)))
                z (range (nth lo 2) (inc (nth hi 2)))]
            [x y z])))

(defn- collapse [node span]
  (cond
    (nil? node) nil
    (tile? node) node
    (= span leaf-span)
    (let [n (* leaf-dim leaf-dim leaf-dim) vs (vals node)]
      (if (and (= n (count node)) (apply = vs)) {:tile (first vs)} node))
    :else
    (let [dim (if (= span upper-span) upper-dim internal-dim)
          child-span (quot span dim)
          collapsed (into {} (map (fn [[i c]] [i (collapse c child-span)]) node))
          n (* dim dim dim)
          vs (map #(when (tile? %) (:tile %)) (vals collapsed))]
      (if (and (= n (count collapsed)) (every? some? vs) (apply = vs))
        {:tile (first vs)}
        collapsed))))

(defn prune
  "Collapse uniform subtrees into tiles. A filled region then costs one entry
  rather than one per voxel, which is the whole reason for the representation."
  [g]
  (update g :vdb/root (fn [root] (into {} (map (fn [[k v]] [k (collapse v upper-span)]) root)))))

(defn tile-count
  [{:vdb/keys [root]}]
  (letfn [(walk [n] (cond (nil? n) 0 (tile? n) 1 (map? n) (reduce + 0 (map walk (vals n))) :else 0))]
    (reduce + 0 (map walk (vals root)))))

(defn leaf-count
  "How many explicit leaf maps the grid holds — what a tile replaces."
  [{:vdb/keys [root]}]
  (letfn [(walk [n span]
            (cond (nil? n) 0
                  (tile? n) 0
                  (= span leaf-span) 1
                  :else (let [dim (if (= span upper-span) upper-dim internal-dim)]
                          (reduce + 0 (map #(walk % (quot span dim)) (vals n))))))]
    (reduce + 0 (map #(walk % upper-span) (vals root)))))

(defn topology-op
  "Combine two grids by their ACTIVE SETS. Values come from `a` where it has
  one, otherwise from `b`."
  [op a b]
  (let [av (into {} (active-voxels a))
        bv (into {} (active-voxels b))
        ks (case op
             :union (into (set (keys av)) (keys bv))
             :intersection (into #{} (filter #(contains? bv %) (keys av)))
             :difference (into #{} (remove #(contains? bv %) (keys av)))
             (throw (ex-info (str "voxel.vdb: no such topology op " (pr-str op)
                                  ". Known: :union, :intersection, :difference")
                             {:op op})))]
    (reduce (fn [g c] (set-voxel g c (get av c (get bv c)))) (grid (:vdb/background a)) ks)))

(defn to-edn
  "The grid as EDN. **Not a .vdb file** — see the namespace docstring."
  [g]
  {:vdb/format :voxel.vdb/edn-v1
   :vdb/background (:vdb/background g)
   :vdb/voxels (vec (sort-by first (map vec (active-voxels g))))})

(defn from-edn [{:vdb/keys [background voxels format]}]
  (when-not (= :voxel.vdb/edn-v1 format)
    (throw (ex-info (str "voxel.vdb/from-edn reads :voxel.vdb/edn-v1, got " (pr-str format)
                         ". This is this library's own format, not OpenVDB's —"
                         " .vdb and .nvdb are neither read nor written here.")
                    {:format format})))
  (reduce (fn [g [c v]] (set-voxel g c v)) (grid background) voxels))
