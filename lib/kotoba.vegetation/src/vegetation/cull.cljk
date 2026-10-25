(ns vegetation.cull
  "Distance-based culling for vegetation instances.

  Restored from `kami-vegetation/src/cull.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  `cull-by-distance` returns the `budget` closest instances to the camera
  (XZ plane), skipping any instance beyond its species' billboard range
  (per `vegetation.lod`). `build-patches`/`patches-in-range`/
  `cull-with-patches` port the Stage-5 spatial-cell patch clustering used
  to whole-cell-reject far cells before per-instance distance sort, for
  the N > ~10k scaling case. Pure data + pure functions; no GPU dispatch."
  (:require [vegetation.species :as species]
            [vegetation.lod :as lod]
            [vegetation.instance :as instance]))

(defn- floor* [x]
  #?(:clj (Math/floor (double x))
     :cljs (js/Math.floor x)))

(defn- sqrt* [x]
  #?(:clj (Math/sqrt (double x))
     :cljs (js/Math.sqrt x)))

(defn- species-of
  "Species keyword from an instance's numeric `:species` field."
  [inst]
  (species/index->species-id (:species inst)))

(defn cull-by-distance
  "Cull + sort by distance. Returns indices into `instances`, closest first.
   Skips instances beyond their species' billboard range."
  [instances cam-x cam-z budget]
  (let [visible (keep-indexed
                 (fn [i inst]
                   (let [[x _ z] (:position inst)
                         dx (- x cam-x)
                         dz (- z cam-z)
                         d2 (+ (* dx dx) (* dz dz))
                         species (species-of inst)
                         tier (lod/classify-lod (sqrt* d2) species)]
                     (when (not= tier :culled)
                       [d2 i])))
                 instances)
        visible (sort-by first visible)
        visible (if (> (count visible) budget)
                  (take budget visible)
                  visible)]
    (mapv second visible)))

(defn cull-to-buffer
  "Convenience: returns the culled instances as a flat f32 buffer
   (8 floats per instance, see `instance/instance->floats`)."
  [instances cam-x cam-z budget]
  (let [idxs (cull-by-distance instances cam-x cam-z budget)]
    (vec (mapcat (fn [i] (instance/instance->floats (nth instances i))) idxs))))

;; ---------------------------------------------------------------------
;; Stage 5: Patch clustering (spatial cell grouping)
;; ---------------------------------------------------------------------
;; A "patch" is a spatial cell containing nearby instance indices, used
;; for batch draw and patch-LOD skipping when an entire cell is
;; off-screen. Patch = {:cell-x :cell-z :center [cx cz] :instances [...]}

(defn build-patches
  "Bin instances into spatial cells of `cell-size` x `cell-size` world
   units. For N=10k instances with cell-size=32, produces ~O(N/cell-area)
   patches. Patches enable whole-cell frustum cull before per-instance
   tests."
  [instances cell-size]
  (let [inv (/ 1.0 cell-size)
        half (* cell-size 0.5)
        grouped (reduce
                 (fn [m [i inst]]
                   (let [[x _ z] (:position inst)
                         cx (long (floor* (* x inv)))
                         cz (long (floor* (* z inv)))]
                     (update m [cx cz] (fnil conj []) i)))
                 {}
                 (map-indexed vector instances))]
    (mapv (fn [[[cx cz] ids]]
            {:cell-x cx
             :cell-z cz
             :center [(+ (* cx cell-size) half) (+ (* cz cell-size) half)]
             :instances ids})
          grouped)))

(defn patches-in-range
  "Fast patch-level cull: reject entire cells beyond `max-dist` from
   camera (XZ plane). Cells with any overlap are kept, passed to
   per-instance cull. Returns indices into `patches`."
  [patches cam-x cam-z max-dist cell-size]
  (let [pad (+ max-dist (* cell-size 0.71))
        max-d2 (* pad pad)]
    (vec (keep-indexed
          (fn [i p]
            (let [[cx cz] (:center p)
                  dx (- cx cam-x)
                  dz (- cz cam-z)]
              (when (< (+ (* dx dx) (* dz dz)) max-d2)
                i)))
          patches))))

(defn cull-with-patches
  "Patch-aware cull: use spatial cells to pre-reject far patches, then do
   per-instance distance sort within remaining patches. This is the
   N > ~10k scaling variant; for N < 5k, `cull-to-buffer` (flat
   iteration) is faster due to cache locality. Returns a flat f32 buffer
   (8 floats per instance)."
  [instances patches cam-x cam-z budget max-dist cell-size]
  (let [nearby (patches-in-range patches cam-x cam-z max-dist cell-size)
        candidates (vec (mapcat #(:instances (nth patches %)) nearby))
        visible (keep (fn [i]
                         (let [inst (nth instances i)
                               [x _ z] (:position inst)
                               dx (- x cam-x)
                               dz (- z cam-z)
                               d2 (+ (* dx dx) (* dz dz))
                               species (species-of inst)]
                           (when (not= (lod/classify-lod (sqrt* d2) species) :culled)
                             [d2 i])))
                       candidates)
        visible (sort-by first visible)
        visible (if (> (count visible) budget) (take budget visible) visible)]
    (vec (mapcat (fn [[_ i]] (instance/instance->floats (nth instances i))) visible))))
