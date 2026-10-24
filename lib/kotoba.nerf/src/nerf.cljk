(ns nerf
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-nerf Rust crate
  (deleted in kotoba-lang/kami-engine PR #82 \"Remove Rust workspace from kami-engine\")
  as part of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root). Native
  execution stays substrate; this namespace owns the CLJC contracts / data
  interpreters / EDN IR for the domain.

  Purpose: loads a pre-trained NeRF density grid (a 3D scalar field of density
  values, plus an optional co-located RGB color field) and samples it into a
  sparse voxel volume by trilinear-interpolating density at every voxel center
  and thresholding. The original Rust crate depended on `kami-voxel` for the
  `VoxelVolume`/`Voxel` output type; since that crate has not yet been restored
  as a CLJC dependency, this namespace ports a minimal self-contained voxel
  volume representation (plain map of `[x y z] -> voxel`) sufficient to satisfy
  `to-volume`'s contract without introducing a hard dependency.")

;; ---------------------------------------------------------------------------
;; Portable math helpers (Vec3 as a plain 3-vector `[x y z]`)
;; ---------------------------------------------------------------------------

(defn- floor*
  [x]
  #?(:clj (Math/floor (double x))
     :cljs (js/Math.floor x)))

(defn fract
  "Fractional part of `x` (matches Rust `f32::fract`: `x - x.trunc()` for x>=0,
  which is what this domain always calls it with)."
  [x]
  (- x (floor* x)))

(defn clamp
  "Clamp `x` into `[lo hi]`."
  [x lo hi]
  (max lo (min x hi)))

(defn v-sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn v-add [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])

(defn v-div
  "Componentwise vector division."
  [[ax ay az] [bx by bz]]
  [(/ ax bx) (/ ay by) (/ az bz)])

(defn v-scale [[x y z] s] [(* x s) (* y s) (* z s)])

(defn v-length
  [[x y z]]
  #?(:clj (Math/sqrt (double (+ (* x x) (* y y) (* z z))))
     :cljs (js/Math.sqrt (+ (* x x) (* y y) (* z z)))))

(def v-zero [0.0 0.0 0.0])

(defn v-splat [s] [s s s])

;; ---------------------------------------------------------------------------
;; DensityGrid — a 3D density field (+ optional co-located color field)
;; ---------------------------------------------------------------------------

(defn make-density-grid
  "Rust `DensityGrid::new`. `data` is a flat (z-major: idx = z*dy*dx + y*dx + x)
  vector of f32 density samples over `dims` = `[dx dy dz]`, spanning the AABB
  `[bounds-min bounds-max]`."
  [data dims bounds-min bounds-max]
  {:data data
   :color-data []
   :dims dims
   :bounds-min bounds-min
   :bounds-max bounds-max})

(defn with-colors
  "Rust `DensityGrid::with_colors` — attach a flat parallel array of `[r g b]`
  colors (same z-major indexing as `:data`). Returns the updated grid."
  [grid colors]
  (assoc grid :color-data colors))

(defn- grid-idx
  "Clamp-and-flatten a grid-space integer coordinate into `:data`."
  [{:keys [data dims]} x y z]
  (let [[dx dy dz] dims
        cx (min x (dec dx))
        cy (min y (dec dy))
        cz (min z (dec dz))]
    (nth data (+ (* cz dy dx) (* cy dx) cx))))

(defn sample
  "Rust `DensityGrid::sample` — trilinear interpolation of density at world
  point `p`."
  [{:keys [dims bounds-min bounds-max] :as grid} p]
  (let [[dx dy dz] dims
        range- (v-sub bounds-max bounds-min)
        norm (v-div (v-sub p bounds-min) range-)
        [nx ny nz] norm
        gx (clamp (* nx (dec dx)) 0.0 (double (dec dx)))
        gy (clamp (* ny (dec dy)) 0.0 (double (dec dy)))
        gz (clamp (* nz (dec dz)) 0.0 (double (dec dz)))
        ix (long gx)
        iy (long gy)
        iz (long gz)
        fx (fract gx)
        fy (fract gy)
        fz (fract gz)
        idx (fn [x y z] (grid-idx grid x y z))]
    (+ (* (idx ix iy iz) (- 1.0 fx) (- 1.0 fy) (- 1.0 fz))
       (* (idx (inc ix) iy iz) fx (- 1.0 fy) (- 1.0 fz))
       (* (idx ix (inc iy) iz) (- 1.0 fx) fy (- 1.0 fz))
       (* (idx (inc ix) (inc iy) iz) fx fy (- 1.0 fz))
       (* (idx ix iy (inc iz)) (- 1.0 fx) (- 1.0 fy) fz)
       (* (idx (inc ix) iy (inc iz)) fx (- 1.0 fy) fz)
       (* (idx ix (inc iy) (inc iz)) (- 1.0 fx) fy fz)
       (* (idx (inc ix) (inc iy) (inc iz)) fx fy fz))))

(defn sample-color
  "Rust `DensityGrid::sample_color` — nearest-neighbor lookup into
  `:color-data`. Returns `[0.5 0.5 0.5]` if there is no color data, or if the
  computed index falls outside `:color-data` (mirrors the Rust bounds check)."
  [{:keys [color-data dims bounds-min bounds-max]} p]
  (if (empty? color-data)
    [0.5 0.5 0.5]
    (let [[dx dy dz] dims
          range- (v-sub bounds-max bounds-min)
          norm (v-div (v-sub p bounds-min) range-)
          [nx ny nz] norm
          round #?(:clj (fn [v] (Math/round (double v)))
                   :cljs (fn [v] (js/Math.round v)))
          ix (long (clamp (round (* nx (dec dx))) 0 (dec dx)))
          iy (long (clamp (round (* ny (dec dy))) 0 (dec dy)))
          iz (long (clamp (round (* nz (dec dz))) 0 (dec dz)))
          idx (+ (* iz dy dx) (* iy dx) ix)]
      (if (< idx (count color-data))
        (nth color-data idx)
        [0.5 0.5 0.5]))))

;; ---------------------------------------------------------------------------
;; Minimal VoxelVolume — sparse `[x y z] -> voxel` map (kami-voxel not yet
;; restored as a CLJC dependency; see namespace docstring)
;; ---------------------------------------------------------------------------

(defn new-dense-volume
  "Rust `VoxelVolume::new_dense` (as used here: an empty sparse volume sized
  `rx` x `ry` x `rz`, populated lazily via `set-voxel`)."
  [rx ry rz]
  {:dims [rx ry rz] :voxels {}})

(defn set-voxel
  "Rust `VoxelVolume::set` — place `voxel` (a map, e.g. `{:material 1 :color
  [r g b a]}`) at grid coordinate `[x y z]`. Returns the updated volume."
  [volume x y z voxel]
  (assoc-in volume [:voxels [x y z]] voxel))

(defn count-filled
  "Rust `VoxelVolume::count_filled` — number of occupied voxels."
  [volume]
  (count (:voxels volume)))

;; ---------------------------------------------------------------------------
;; DensityGrid -> VoxelVolume
;; ---------------------------------------------------------------------------

(defn to-volume
  "Rust `DensityGrid::to_volume` — sample the grid at the center of every cell
  of a `resolution`^3 voxel volume; cells whose density is `>= threshold` are
  filled with `:material 1` and the grid's interpolated color (opaque)."
  [{:keys [bounds-min bounds-max] :as grid} resolution threshold]
  (let [range- (v-sub bounds-max bounds-min)
        step (v-scale range- (/ 1.0 resolution))
        [sx sy sz] step
        [minx miny minz] bounds-min]
    (reduce
     (fn [volume [x y z]]
       (let [p [(+ minx (* (+ x 0.5) sx))
                (+ miny (* (+ y 0.5) sy))
                (+ minz (* (+ z 0.5) sz))]]
         (if (>= (sample grid p) threshold)
           (let [[r g b] (sample-color grid p)]
             (set-voxel volume x y z {:material 1 :color [r g b 1.0]}))
           volume)))
     (new-dense-volume resolution resolution resolution)
     (for [z (range resolution) y (range resolution) x (range resolution)]
       [x y z]))))
