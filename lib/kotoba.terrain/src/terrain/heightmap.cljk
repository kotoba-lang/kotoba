(ns terrain.heightmap
  "Heightmap: 2D grid of elevation values generated via FBM noise.

  Restored from kotoba-lang/kami-engine's kami-terrain/src/heightmap.rs (deleted
  in PR #82 \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root). Decima-style clipmap design:
  each LOD level is a fixed-size grid centered on the camera, with coarser
  resolution at greater distances. A heightmap here is a plain map
  {:width :depth :data :config} where `:data` is a row-major (z*width+x) vector
  of floats."
  (:require [terrain.noise :as noise]))

(defn- floor [x] #?(:clj (Math/floor x) :cljs (js/Math.floor x)))
(defn- sqrt* [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(defn- clamp [x lo hi] (max lo (min hi x)))

(def default-config
  "Default heightmap generation params, mirroring Rust's HeightmapConfig::default()."
  {:seed 0.0
   :max-height 120.0
   :frequency 0.005
   :octaves 6
   :lacunarity 2.0
   :persistence 0.5})

(defn generate
  "Generate a heightmap for a terrain patch at world origin (wx, wz)."
  [width depth wx wz config]
  (let [{:keys [seed max-height frequency octaves lacunarity persistence]} config
        data (vec (for [z (range depth)
                         x (range width)]
                     (let [world-x (+ wx (double x))
                           world-z (+ wz (double z))
                           nx (+ (* world-x frequency) seed)
                           nz (+ (* world-z frequency) (* seed 0.7))
                           h (noise/fbm-noise nx nz octaves lacunarity persistence)
                           ;; smoothstep: flatten valleys, sharpen peaks (Decima-style)
                           curved (* h h (- 3.0 (* 2.0 h)))]
                       (* curved max-height))))]
    {:width width :depth depth :data data :config config}))

(defn sample
  "Sample height at fractional position with bilinear interpolation."
  [{:keys [width depth data]} x z]
  (let [x (clamp x 0.0 (double (dec width)))
        z (clamp z 0.0 (double (dec depth)))
        fx (floor x)
        fz (floor z)
        xi (long fx)
        zi (long fz)
        xf (- x fx)
        zf (- z fz)
        x0 (min xi (dec width))
        x1 (min (inc xi) (dec width))
        z0 (min zi (dec depth))
        z1 (min (inc zi) (dec depth))
        h00 (nth data (+ (* z0 width) x0))
        h10 (nth data (+ (* z0 width) x1))
        h01 (nth data (+ (* z1 width) x0))
        h11 (nth data (+ (* z1 width) x1))
        ix0 (+ (* h00 (- 1.0 xf)) (* h10 xf))
        ix1 (+ (* h01 (- 1.0 xf)) (* h11 xf))]
    (+ (* ix0 (- 1.0 zf)) (* ix1 zf))))

(defn normal
  "Compute the surface normal at a grid point via central differences."
  [{:keys [width depth data]} x z]
  (let [at (fn [cx cz] (nth data (+ (* cz width) cx)))
        x0 (if (pos? x) (dec x) 0)
        x1 (min (inc x) (dec width))
        z0 (if (pos? z) (dec z) 0)
        z1 (min (inc z) (dec depth))
        dx (- (at x1 z) (at x0 z))
        dz (- (at x z1) (at x z0))
        nx (- dx)
        ny 2.0
        nz (- dz)
        len (sqrt* (+ (* nx nx) (* ny ny) (* nz nz)))]
    [(/ nx len) (/ ny len) (/ nz len)]))
