(ns game.voxel
  "Voxel volume storage: block types, chunk management, KAMI Column serialization,
  game-specific tuning.

  Restored from kami-game's `voxel.rs` (kotoba-lang/kami-engine, deleted in
  PR #82 \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root).

  This is a distinct, smaller module from the already-restored
  `kotoba-lang/voxel` (ported from `kami-voxel`, the full storage-backend
  system). `kami-game`'s `voxel.rs` is a self-contained 16^3 fixed-size
  chunk + sparse chunked world with a 16-entry block-type palette, used
  directly by game scenes — it shares no types with `kotoba-lang/voxel`;
  ported here as its own thing.

  A `VoxelChunk` is a plain map:
    {:blocks [u8 ...]  ; len = CHUNK-VOLUME (4096), row-major y*256 + z*16 + x
     :dirty  bool}

  A `VoxelWorld` is a plain map:
    {:chunks  {[cx cy cz] chunk, ...}
     :palette [[r g b a] ...]}

  All chunk/world mutation is pure (functions return the updated value;
  no in-place `set!`).")

;; ---------------------------------------------------------------------
;; BlockType
;; ---------------------------------------------------------------------

(def CHUNK-SIZE 16)
(def CHUNK-VOLUME (* CHUNK-SIZE CHUNK-SIZE CHUNK-SIZE))

(def block-type->u8
  {:air 0 :dirt 1 :grass 2 :stone 3 :water 4 :sand 5 :wood 6 :leaf 7
   :ore 8 :brick 9 :glass 10 :metal 11 :snow 12 :lava 13 :ice 14 :gravel 15})

(def u8->block-type
  (into {} (map (fn [[k v]] [v k]) block-type->u8)))

(defn block-from-u8
  [v]
  (get u8->block-type v :air))

(defn block-solid?
  [block]
  (not= block :air))

(defn block-transparent?
  [block]
  (contains? #{:air :water :glass :ice} block))

;; ---------------------------------------------------------------------
;; VoxelChunk
;; ---------------------------------------------------------------------

(defn voxel-chunk
  "New chunk, all air, dirty."
  []
  {:blocks (vec (repeat CHUNK-VOLUME 0))
   :dirty true})

(defn solid-chunk
  "New chunk filled entirely with `block`."
  [block]
  {:blocks (vec (repeat CHUNK-VOLUME (block-type->u8 block)))
   :dirty true})

(defn- chunk-index
  [x y z]
  (+ (* y CHUNK-SIZE CHUNK-SIZE) (* z CHUNK-SIZE) x))

(defn- chunk-in-bounds? [x y z]
  (and (>= x 0) (>= y 0) (>= z 0) (< x CHUNK-SIZE) (< y CHUNK-SIZE) (< z CHUNK-SIZE)))

(defn chunk-get
  [chunk x y z]
  (if (chunk-in-bounds? x y z)
    (block-from-u8 (nth (:blocks chunk) (chunk-index x y z)))
    :air))

(defn chunk-set
  "Returns an updated chunk with (x,y,z) set to `block` (dirty := true).
  Out-of-bounds coordinates are a no-op (returns `chunk` unchanged)."
  [chunk x y z block]
  (if (chunk-in-bounds? x y z)
    (-> chunk
        (assoc :blocks (assoc (:blocks chunk) (chunk-index x y z) (block-type->u8 block)))
        (assoc :dirty true))
    chunk))

(defn chunk-dirty?
  [chunk]
  (:dirty chunk))

(defn chunk-clear-dirty
  [chunk]
  (assoc chunk :dirty false))

(defn chunk->column
  "Serialize to KAMI Column data (U8, stride 1, len = CHUNK-VOLUME)."
  [chunk]
  (:blocks chunk))

(defn column->chunk
  "Deserialize from KAMI Column data."
  [data]
  (let [data (vec data)
        len (min (count data) CHUNK-VOLUME)
        blocks (vec (concat (subvec data 0 len) (repeat (- CHUNK-VOLUME len) 0)))]
    {:blocks blocks :dirty true}))

(defn chunk-solid-count
  "Count non-air blocks."
  [chunk]
  (count (remove zero? (:blocks chunk))))

;; ---------------------------------------------------------------------
;; Palette
;; ---------------------------------------------------------------------

(defn default-palette
  "Default block palette: index (block u8) → RGBA color."
  []
  [[0.0 0.0 0.0 0.0]     ; Air (transparent)
   [0.55 0.35 0.2 1.0]   ; Dirt
   [0.3 0.6 0.2 1.0]     ; Grass
   [0.5 0.5 0.5 1.0]     ; Stone
   [0.2 0.3 0.8 0.7]     ; Water
   [0.85 0.75 0.5 1.0]   ; Sand
   [0.45 0.3 0.15 1.0]   ; Wood
   [0.2 0.5 0.1 0.9]     ; Leaf
   [0.6 0.5 0.3 1.0]     ; Ore
   [0.7 0.3 0.2 1.0]     ; Brick
   [0.8 0.9 1.0 0.4]     ; Glass
   [0.7 0.7 0.75 1.0]    ; Metal
   [0.95 0.95 1.0 1.0]   ; Snow
   [1.0 0.3 0.0 1.0]     ; Lava
   [0.6 0.8 1.0 0.8]     ; Ice
   [0.6 0.55 0.5 1.0]])  ; Gravel

;; ---------------------------------------------------------------------
;; VoxelWorld
;; ---------------------------------------------------------------------

(defn voxel-world
  []
  {:chunks {} :palette (default-palette)})

(defn- div-euclid
  [a b]
  (long (Math/floor (/ (double a) (double b)))))

(defn- rem-euclid
  "Clojure's `mod` already floors toward -infinity for positive `b`,
  matching Rust's `rem_euclid` (always non-negative)."
  [a b]
  (mod a b))

(defn- chunk-coords
  [wx wy wz]
  [[(div-euclid wx CHUNK-SIZE) (div-euclid wy CHUNK-SIZE) (div-euclid wz CHUNK-SIZE)]
   [(rem-euclid wx CHUNK-SIZE) (rem-euclid wy CHUNK-SIZE) (rem-euclid wz CHUNK-SIZE)]])

(defn world-set-block
  [world wx wy wz block]
  (let [[ckey [lx ly lz]] (chunk-coords wx wy wz)
        chunk (get-in world [:chunks ckey] (voxel-chunk))
        chunk' (chunk-set chunk lx ly lz block)]
    (assoc-in world [:chunks ckey] chunk')))

(defn world-get-block
  [world wx wy wz]
  (let [[ckey [lx ly lz]] (chunk-coords wx wy wz)
        chunk (get-in world [:chunks ckey])]
    (if chunk (chunk-get chunk lx ly lz) :air)))

(defn world-dirty-chunks
  [world]
  (->> (:chunks world)
       (filter (fn [[_ c]] (chunk-dirty? c)))
       (map first)
       vec))

(defn generate-flat
  "Generate flat terrain: layers of stone/dirt/grass."
  [width depth height]
  (reduce
   (fn [world y]
     (let [block (cond
                   (< y (- height 2)) :stone
                   (< y (- height 1)) :dirt
                   :else :grass)]
       (reduce
        (fn [world [z x]] (world-set-block world x y z block))
        world
        (for [z (range depth) x (range width)] [z x]))))
   (voxel-world)
   (range height)))
