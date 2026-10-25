(ns game.terrain
  "Heightmap terrain generation and LOD mesh output, game-specific tuning.

  Restored from kami-game's `terrain.rs` (kotoba-lang/kami-engine, deleted
  in PR #82 \"Remove Rust workspace from kami-engine\") as part of the
  clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  This is a distinct, smaller module from the already-restored
  `kotoba-lang/terrain` (ported from `kami-terrain`, the full FBM/biome/
  heightmap system used by the broader KAMI world). `kami-game`'s
  `terrain.rs` is a self-contained heightmap→mesh pipeline with its own
  bilinear sampler, LOD mesh builder, and a tiny built-in value-noise
  generator (no external noise crate) plus an R16 raw heightmap loader —
  used directly by game scenes rather than the full terrain system. It
  shares no types with `kotoba-lang/terrain`; ported here as its own thing.

  A `HeightmapTerrain` is a plain map:
    {:heights      [f32 ...]   ; row-major, len = width*depth
     :width        u32
     :depth        u32
     :height-scale f32
     :cell-size    f32}

  A `TerrainMesh` is a plain map:
    {:vertices     [f32 ...]   ; interleaved pos3+norm3+uv2 = 8 floats/vertex
     :indices      [u32 ...]
     :vertex-count u32
     :index-count  u32}

  The value-noise generator in `from-noise` uses the same 64-bit LCG
  wraparound arithmetic as the original Rust `wrapping_mul`/`wrapping_add`
  (JVM `unchecked-*` ops on `long` share the 2's-complement bit pattern),
  matching the pattern already established in `kotoba-lang/yield` and
  `kotoba-lang/vegetation`.")

;; ---------------------------------------------------------------------
;; Construction
;; ---------------------------------------------------------------------

(defn heightmap-terrain
  "New flat (all-zero) terrain of `width` x `depth`."
  [width depth height-scale cell-size]
  {:heights (vec (repeat (* width depth) 0.0))
   :width width
   :depth depth
   :height-scale height-scale
   :cell-size cell-size})

(defn- height-at
  "Height at grid position (x, z), or 0.0 if out of bounds."
  [{:keys [heights width depth height-scale]} x z]
  (if (and (< x width) (< z depth))
    (* (nth heights (+ (* z width) x)) height-scale)
    0.0))

;; ---------------------------------------------------------------------
;; Sampling
;; ---------------------------------------------------------------------

(defn- clampi
  [v mx]
  (-> v (max 0) (min (dec mx))))

(defn sample-height
  "Sample height at world position with bilinear interpolation."
  [terrain wx wz]
  (let [{:keys [width depth cell-size]} terrain
        gx (/ wx cell-size)
        gz (/ wz cell-size)
        x0 (long (Math/floor gx))
        z0 (long (Math/floor gz))
        fx (- gx (Math/floor gx))
        fz (- gz (Math/floor gz))
        h00 (height-at terrain (clampi x0 width) (clampi z0 depth))
        h10 (height-at terrain (clampi (inc x0) width) (clampi z0 depth))
        h01 (height-at terrain (clampi x0 width) (clampi (inc z0) depth))
        h11 (height-at terrain (clampi (inc x0) width) (clampi (inc z0) depth))
        a (+ (* h00 (- 1.0 fx)) (* h10 fx))
        b (+ (* h01 (- 1.0 fx)) (* h11 fx))]
    (+ (* a (- 1.0 fz)) (* b fz))))

;; ---------------------------------------------------------------------
;; Mesh generation
;; ---------------------------------------------------------------------

(defn to-mesh-lod
  "Generate mesh at given LOD level. Level 0 = full, each level halves resolution."
  [terrain lod-level]
  (let [{:keys [width depth cell-size]} terrain
        step (bit-shift-left 1 lod-level)
        cols (inc (quot (dec width) step))
        rows (inc (quot (dec depth) step))
        positions (transient [])
        normals (transient [])
        uvs (transient [])]
    (doseq [iz (range rows)
            ix (range cols)]
      (let [gx (min (* ix step) (dec width))
            gz (min (* iz step) (dec depth))
            x (* (double gx) cell-size)
            z (* (double gz) cell-size)
            y (height-at terrain gx gz)]
        (conj! positions x) (conj! positions y) (conj! positions z)
        (conj! uvs (/ (double gx) (double (max (dec width) 1))))
        (conj! uvs (/ (double gz) (double (max (dec depth) 1))))
        (let [hx0 (if (pos? gx) (height-at terrain (dec gx) gz) y)
              hx1 (if (< (inc gx) width) (height-at terrain (inc gx) gz) y)
              hz0 (if (pos? gz) (height-at terrain gx (dec gz)) y)
              hz1 (if (< (inc gz) depth) (height-at terrain gx (inc gz)) y)
              dx (- hx1 hx0)
              dz (- hz1 hz0)
              nx (- dx)
              ny (* 2.0 cell-size)
              nz (- dz)
              len (Math/sqrt (+ (* nx nx) (* ny ny) (* nz nz)))]
          (conj! normals (/ nx len)) (conj! normals (/ ny len)) (conj! normals (/ nz len)))))
    (let [positions (persistent! positions)
          normals (persistent! normals)
          uvs (persistent! uvs)
          indices (transient [])]
      (doseq [iz (range (dec rows))
              ix (range (dec cols))]
        (let [a (+ (* iz cols) ix)
              b (+ a cols)]
          (conj! indices a) (conj! indices b) (conj! indices (inc a))
          (conj! indices (inc a)) (conj! indices b) (conj! indices (inc b))))
      (let [indices (persistent! indices)
            vertex-count (* cols rows)
            index-count (count indices)
            vertices (transient [])]
        (dotimes [i vertex-count]
          (dotimes [k 3] (conj! vertices (nth positions (+ (* i 3) k))))
          (dotimes [k 3] (conj! vertices (nth normals (+ (* i 3) k))))
          (dotimes [k 2] (conj! vertices (nth uvs (+ (* i 2) k)))))
        {:vertices (persistent! vertices)
         :indices indices
         :vertex-count vertex-count
         :index-count index-count}))))

(defn to-mesh
  "Generate full-resolution mesh."
  [terrain]
  (to-mesh-lod terrain 0))

;; ---------------------------------------------------------------------
;; Generators (no external noise dependency)
;; ---------------------------------------------------------------------

(def ^:private U64-MASK 0xffffffffffffffff)

(defn- lcg-next
  "One LCG step matching Rust's `wrapping_mul`/`wrapping_add` on u64.
  Returns the new state (a `long`, 2's-complement bit-identical to the u64)."
  [state]
  (unchecked-add (unchecked-multiply state 6364136223846793005) 1442695040888963407))

(defn from-noise
  "Generate terrain from simple hash-based value noise (no external dependency)."
  [width depth seed]
  (let [heights (transient (vec (repeat (* width depth) 0.0)))]
    (loop [z 0 rng seed]
      (if (>= z depth)
        {:heights (persistent! heights)
         :width width :depth depth :height-scale 1.0 :cell-size 1.0}
        (let [rng (loop [x 0 rng rng]
                     (if (>= x width)
                       rng
                       (let [rng' (lcg-next rng)
                             r (/ (double (unsigned-bit-shift-right rng' 33))
                                  (double 0xffffffff))
                             fx (/ (double x) (double width))
                             fz (/ (double z) (double depth))
                             h (+ (* r 0.3)
                                  (* (Math/sin (* fx 3.14 2.0)) 0.2)
                                  (* (Math/cos (* fz 3.14 3.0)) 0.15)
                                  (* (Math/sin (* (+ fx fz) 3.14 5.0)) 0.1))]
                         (assoc! heights (+ (* z width) x) (max h 0.0))
                         (recur (inc x) rng'))))]
          (recur (inc z) rng))))))

#?(:clj
   (defn from-r16
     "Generate from raw R16 heightmap data (16-bit unsigned, little-endian).
     `data` is a byte array or seqable of bytes (0-255 each)."
     [data width depth height-scale]
     (let [data (vec data)
           expected (* width depth 2)
           len (min (count data) expected)
           heights (transient (vec (repeat (* width depth) 0.0)))]
       (dotimes [i (quot len 2)]
         (let [b0 (bit-and (nth data (* i 2)) 0xff)
               b1 (bit-and (nth data (inc (* i 2))) 0xff)
               val (bit-or b0 (bit-shift-left b1 8))]
           (assoc! heights i (/ (double val) 65535.0))))
       {:heights (persistent! heights)
        :width width :depth depth :height-scale height-scale :cell-size 1.0}))
   :cljs
   (defn from-r16
     "Generate from raw R16 heightmap data (16-bit unsigned, little-endian).
     `data` is a seqable of bytes (0-255 each)."
     [data width depth height-scale]
     (let [data (vec data)
           expected (* width depth 2)
           len (min (count data) expected)
           heights (transient (vec (repeat (* width depth) 0.0)))]
       (dotimes [i (quot len 2)]
         (let [b0 (bit-and (nth data (* i 2)) 0xff)
               b1 (bit-and (nth data (inc (* i 2))) 0xff)
               val (bit-or b0 (bit-shift-left b1 8))]
           (assoc! heights i (/ (double val) 65535.0))))
       {:heights (persistent! heights)
        :width width :depth depth :height-scale height-scale :cell-size 1.0})))
