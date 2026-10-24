(ns kotoba.geo.noise
  "Procedural value-noise / fBm used by `kotoba.geo.mesh/globe-relief-height`
  to fake terrain relief on the globe view when no DEM is supplied.

  Ported from the private helpers at the bottom of
  kami-engine/kami-geo/src/mesh.rs (`fbm2`, `ridged_fbm2`, `value_noise2`,
  `hash2`, `globe_relief_height`) — Rust source deleted from the working
  tree pre-commit; recovered from git history.

  `hash2` reproduces Rust's `u32::wrapping_mul` + bit-shift hash bit-exactly
  on both JVM (64-bit `long` masked to 32 bits after each multiply) and
  ClojureScript (`Math.imul`, which is natively 32-bit wrapping)."
  (:require [kotoba.geo.constants :as k]
            [kotoba.geo.math :as math]))

(defn- mul32
  "32-bit wrapping multiply, portable across JVM longs and JS int32s."
  [a b]
  #?(:clj (bit-and (unchecked-multiply (long a) (long b)) 0xFFFFFFFF)
     :cljs (js/Math.imul a b)))

(defn- hash2 [x y]
  (let [n0 (bit-xor (mul32 x 374761393) (mul32 y 668265263))
        n1 (mul32 (bit-xor n0 (unsigned-bit-shift-right n0 13)) 1274126177)
        n2 (bit-xor n1 (unsigned-bit-shift-right n1 16))]
    (/ (double (unsigned-bit-shift-right n2 0)) 4294967295.0)))

(defn lerp [a b t] (+ a (* (- b a) t)))

(defn smoothstep [edge0 edge1 x]
  (let [t (math/clamp (/ (- x edge0) (- edge1 edge0)) 0.0 1.0)]
    (* t t (- 3.0 (* 2.0 t)))))

(defn value-noise2 [x y]
  (let [x0 (math/floor x)
        y0 (math/floor y)
        tx (- x x0)
        ty (- y y0)
        sx (smoothstep 0.0 1.0 tx)
        sy (smoothstep 0.0 1.0 ty)
        ix0 (long x0)
        iy0 (long y0)
        n00 (hash2 ix0 iy0)
        n10 (hash2 (inc ix0) iy0)
        n01 (hash2 ix0 (inc iy0))
        n11 (hash2 (inc ix0) (inc iy0))
        nx0 (lerp n00 n10 sx)
        nx1 (lerp n01 n11 sx)]
    (lerp nx0 nx1 sy)))

(defn fbm2 [x y octaves lacunarity gain]
  (loop [i 0 x x y y amp 0.5 sum 0.0 norm 0.0]
    (if (>= i octaves)
      (if (> norm 0.0) (/ sum norm) 0.0)
      (recur (inc i) (* x lacunarity) (* y lacunarity) (* amp gain)
             (+ sum (* amp (value-noise2 x y)))
             (+ norm amp)))))

(defn ridged-fbm2 [x y octaves lacunarity gain]
  (loop [i 0 x x y y amp 0.5 sum 0.0 norm 0.0]
    (if (>= i octaves)
      (if (> norm 0.0) (/ sum norm) 0.0)
      (let [n (- 1.0 (math/abs (- (* (value-noise2 x y) 2.0) 1.0)))]
        (recur (inc i) (* x lacunarity) (* y lacunarity) (* amp gain)
               (+ sum (* amp n n))
               (+ norm amp))))))

(defn globe-relief-height
  "Procedural terrain relief in [-ish, ~1] used when no DEM is available."
  [lng lat]
  (let [{:keys [continent shelf ridges hills ocean]} (:relief k/constants)
        x (/ lng 180.0)
        y (/ lat 90.0)
        lat-band (- 1.0 (math/pow (/ (math/abs lat) 90.0) 1.35))
        cont (fbm2 (+ (* x 1.15) 13.7) (- (* y 1.15) 5.4)
                    (:octaves continent) (:lacunarity continent) (:gain continent))
        shelf-v (fbm2 (- (* x 2.6) 8.1) (+ (* y 2.6) 4.7)
                       (:octaves shelf) (:lacunarity shelf) (:gain shelf))
        land-mask (smoothstep -0.08 0.22
                               (+ (* cont 0.9) (* shelf-v 0.35) (* lat-band 0.14)))
        ridge-v (ridged-fbm2 (+ (* x 6.5) 1.9) (- (* y 6.5) 3.7)
                              (:octaves ridges) (:lacunarity ridges) (:gain ridges))
        hills-v (fbm2 (- (* x 9.0) 12.3) (+ (* y 9.0) 2.8)
                       (:octaves hills) (:lacunarity hills) (:gain hills))
        ocean-v (fbm2 (+ (* x 4.2) 6.6) (- (* y 4.2) 1.1)
                       (:octaves ocean) (:lacunarity ocean) (:gain ocean))
        mountains (* (math/pow land-mask 2.2) (math/pow ridge-v 1.7))
        uplands (* land-mask (+ 0.18 (* hills-v 0.28)))
        ocean-depth (* (- (- 1.0 land-mask)) (+ 0.12 (* 0.08 ocean-v)))]
    (+ uplands (* mountains 0.72) ocean-depth)))
