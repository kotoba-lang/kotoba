(ns terrain.noise
  "Value noise + FBM (Fractal Brownian Motion) for terrain generation.

  Restored from kotoba-lang/kami-engine's kami-terrain/src/noise.rs (deleted in
  PR #82 \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root). Uses hash-based value noise
  (not gradient/Perlin noise) to avoid US10232272B2 patent risk, matching the
  original design. Zero-dep, pure functions, portable CLJ/CLJS.")

(defn- floor [x] #?(:clj (Math/floor x) :cljs (js/Math.floor x)))
(defn- cos* [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))
(def ^:private PI #?(:clj Math/PI :cljs js/Math.PI))

(defn- imul32
  "32-bit wrapping multiply, matching Rust's i32::wrapping_mul."
  [a b]
  #?(:clj (unchecked-multiply-int (unchecked-int a) (unchecked-int b))
     :cljs (js/Math.imul a b)))

(defn- wrap32
  "Truncate/wrap an integer to signed 32-bit range, matching Rust's i32 overflow semantics."
  [n]
  #?(:clj (unchecked-int n)
     :cljs (bit-or n 0)))

(defn- hash2d
  "Hash-based value noise at integer coordinates. Deterministic, mapped to [0, 1]."
  [x y]
  (let [n (wrap32 (+ (imul32 x 1619) (imul32 y 31337)))
        n (imul32 n (imul32 n n))
        n (bit-xor (bit-shift-right n 13) n)
        n (wrap32 (+ (imul32 n (wrap32 (+ (imul32 n (imul32 n 60493)) 19990303)))
                      1376312589))]
    (/ (double (bit-and n 0x7fffffff)) (double 0x7fffffff))))

(defn- cosine-interp
  "Cosine interpolation for smooth transitions."
  [a b t]
  (let [ft (* t PI)
        f (* 0.5 (- 1.0 (cos* ft)))]
    (+ (* a (- 1.0 f)) (* b f))))

(defn value-noise
  "2D value noise with cosine interpolation."
  [x y]
  (let [fx (floor x)
        fy (floor y)
        xi (long fx)
        yi (long fy)
        xf (- x fx)
        yf (- y fy)
        v00 (hash2d xi yi)
        v10 (hash2d (inc xi) yi)
        v01 (hash2d xi (inc yi))
        v11 (hash2d (inc xi) (inc yi))
        ix0 (cosine-interp v00 v10 xf)
        ix1 (cosine-interp v01 v11 xf)]
    (cosine-interp ix0 ix1 yf)))

(defn fbm-noise
  "Fractal Brownian Motion: layered value noise for terrain height.

  `octaves`: number of noise layers (4-8 typical)
  `lacunarity`: frequency multiplier per octave (typically 2.0)
  `persistence`: amplitude multiplier per octave (typically 0.5)"
  [x y octaves lacunarity persistence]
  (loop [i 0
         value 0.0
         amplitude 1.0
         frequency 1.0
         max-amplitude 0.0]
    (if (< i octaves)
      (recur (inc i)
             (+ value (* amplitude (value-noise (* x frequency) (* y frequency))))
             (* amplitude persistence)
             (* frequency lacunarity)
             (+ max-amplitude amplitude))
      (/ value max-amplitude))))
