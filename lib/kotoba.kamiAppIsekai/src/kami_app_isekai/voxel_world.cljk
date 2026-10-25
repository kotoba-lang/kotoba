(ns kami-app-isekai.voxel-world
  "Deterministic voxel-world generation rules for the ISEKAI demo:
  2-octave value noise, palette, terrain height rule, and the
  pre-authored demo-house layout. Restored from kami-app-isekai's
  `lib.rs` (kami-engine/kami-app-isekai, deleted PR #82).

  The original crate's `build_voxel_world`/`build_demo_house` mutated a
  native `kami_pipelines::VoxelChunkAdapter` (chunk streaming, GPU
  upload) as a side effect of computing these values — this namespace
  ports only the PURE computation (given a world coordinate, which
  palette index — if any — occupies it), leaving native chunk
  management/GPU upload out of scope.")

(def palette-air 0)
(def palette-wood 1)
(def palette-grass 2)
(def palette-stone 3)
(def palette-sand 4)
(def palette-brick 5)
(def palette-glass 6)
(def palette-fire 7)
(def palette-paper 8)
(def palette-ash 9)
(def palette-water 10)

(def isekai-palette
  "RGB color table indexed by palette id 0-10."
  [[0.0 0.0 0.0]      ;; 0 air (unused)
   [0.55 0.35 0.2]    ;; 1 wood
   [0.2 0.7 0.25]     ;; 2 grass
   [0.5 0.5 0.55]     ;; 3 stone
   [0.9 0.88 0.8]     ;; 4 sand
   [0.82 0.25 0.2]    ;; 5 brick
   [0.4 0.8 0.9]      ;; 6 glass
   [1.0 0.45 0.1]     ;; 7 fire (vivid orange, emits heat)
   [0.96 0.94 0.88]   ;; 8 paper (ivory)
   [0.25 0.22 0.2]    ;; 9 ash
   [0.12 0.36 0.65]]) ;; 10 water (emits moisture)

(defn- frac [x] (- x (Math/floor x)))

(defn- hash-noise
  "Deterministic value-noise hash at integer lattice point `(x,z)`, no
  std-rand, matching the original's sin-based hash."
  [x z]
  (let [sx (* (Math/sin (+ (* x 12.9898) (* z 78.233))) 43758.547)]
    (frac sx)))

(defn simple-fbm
  "2-octave deterministic value noise at `(x,z)` (matches the pattern
  used in kami-terrain::noise but small + inline)."
  [x z]
  (let [fx0 (Math/floor x) fz0 (Math/floor z)
        v0 (hash-noise fx0 fz0)
        v1 (hash-noise (+ fx0 1.0) fz0)
        v2 (hash-noise fx0 (+ fz0 1.0))
        v3 (hash-noise (+ fx0 1.0) (+ fz0 1.0))
        fx (frac x) fz (frac z)
        ix0 (+ (* v0 (- 1.0 fx)) (* v1 fx))
        ix1 (+ (* v2 (- 1.0 fx)) (* v3 fx))]
    (+ (* ix0 (- 1.0 fz)) (* ix1 fz))))

(def terrain-height-min
  "Analytic lower bound of `terrain-height`'s output: `simple-fbm` is a
  bilinear blend of `hash-noise` values, each confined to [0,1) by `frac`,
  so the blend itself is confined to [0,1) — at amplitude 12 and baseline
  18 (below) that puts `terrain-height` in `[18.0, 30.0)`."
  18.0)

(def terrain-height-max
  "Analytic (open) upper bound of `terrain-height`'s output — see
  `terrain-height-min`."
  30.0)

(defn terrain-height
  "World-space terrain surface height at `(wx wz)`: a coarse 2-octave FBM
  ridge around a baseline of 18.0 with amplitude 12.0 (so the output is
  confined to `[terrain-height-min, terrain-height-max)`), matching the
  Plains terrain silhouette roughly. Factored out of `terrain-voxel-at`
  (which still uses it column-by-column to place stone/grass/air) so it
  can be sampled directly as a `(x,z) -> height` heightmap, e.g. for a
  top-down visualization, without walking every voxel y-layer."
  [wx wz]
  (+ (* (simple-fbm (* wx 0.02) (* wz 0.02)) 12.0) 18.0))

(defn terrain-voxel-at
  "Palette index for the terrain-generation rule at local voxel coords
  `(lx ly lz)` within a chunk whose world origin is `[ox oy oz]`, or
  nil for air. Bedrock floor layer shaped by `terrain-height`'s coarse FBM
  height, matching the Plains terrain silhouette roughly."
  [[ox oy oz] lx ly lz]
  (let [wx (+ ox lx) wz (+ oz lz) wy (+ oy ly)
        h (terrain-height wx wz)]
    (cond
      (< wy (- h 3.0)) palette-stone
      (< wy h) palette-grass
      :else nil)))

(defn demo-house-voxels
  "The pre-authored demo house layout: a vector of `[x y z palette-id]`
  local-voxel placements (16x16 footprint, walls to y=4, glass window
  gaps, a single stone pillar, and the v3 DEC compositional fire/paper/
  water-bucket demo row). World origin is `[-16.0 32.0 16.0]` (chunk
  coord `(-1 2 1)`) in the original."
  []
  (vec
   (concat
    ;; floor: stone border, grass interior
    (for [z (range 16) x (range 16)
          :let [edge? (or (= x 0) (= x 15) (= z 0) (= z 15))]]
      [x 0 z (if edge? palette-stone palette-grass)])
    ;; walls y=1..4: brick perimeter, with a door gap on x=15 face at y<=3
    (mapcat
     (fn [y]
       (concat
        (for [i (range 16)] [i y 0 palette-brick])
        (for [i (range 16)] [i y 15 palette-brick])
        (for [i (range 16)] [0 y i palette-brick])
        (for [i (range 16)] [15 y i palette-brick])
        (when (<= y 3)
          [[15 y 7 palette-air] [15 y 8 palette-air]])))
     (range 1 5))
    ;; window glass strips at y=3
    (mapcat
     (fn [j] [[j 3 0 palette-glass] [j 3 15 palette-glass] [0 3 j palette-glass]])
     (range 6 10))
    ;; single stone pillar y=6..9 at (2,y,2)
    (for [y (range 6 10)] [2 y 2 palette-stone])
    ;; DEC demo row: fire, paper line, water bucket
    [[4 1 2 palette-fire] [4 2 2 palette-fire]]
    (for [dx (range 8)] [(+ 5 dx) 1 2 palette-paper])
    [[8 2 2 palette-water] [9 2 2 palette-water]])))

(def plains-terrain-config
  "Adapter config for the shared Plains terrain (biome \"plains\", sea
  level 42.0, 128m chunks, view radius 2). Shared by the main entry and
  the omniverse scene."
  {:biome "plains" :sea-level 42.0 :chunk-size 128 :view-radius 2})
