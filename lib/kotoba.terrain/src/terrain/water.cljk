(ns terrain.water
  "Water plane: flat mesh at sea level with Gerstner wave animation parameters.

  Restored from kotoba-lang/kami-engine's kami-terrain/src/water.rs (deleted in
  PR #82 \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root). Decima-style water:
  Gerstner wave sum evaluated on the GPU; this namespace generates the flat
  base grid on the CPU and derives Gerstner wave parameter sets (either fixed
  defaults or from a wind vector via a simplified Beaufort sea-state
  mapping).")

(defn- sqrt* [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(defn- cos* [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))
(defn- sin* [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))
(def ^:private PI #?(:clj Math/PI :cljs js/Math.PI))
(def ^:private TAU (* 2.0 PI))

(defn- sq [x] (* x x))

(defn default-waves
  "Default ocean wave set (calm seas, Beaufort 3 breeze from the east)."
  []
  [{:direction [0.8 0.6] :amplitude 0.8 :wavelength 60.0 :speed 12.0 :steepness 0.4}
   {:direction [-0.3 0.95] :amplitude 0.4 :wavelength 30.0 :speed 8.0 :steepness 0.3}
   {:direction [0.5 -0.87] :amplitude 0.2 :wavelength 15.0 :speed 5.0 :steepness 0.5}
   {:direction [-0.7 -0.7] :amplitude 0.1 :wavelength 8.0 :speed 3.0 :steepness 0.2}])

(defn default-config
  "Default water configuration, mirroring Rust's WaterConfig::default()."
  []
  {:sea-level 18.0
   :extent 512.0
   :resolution 128
   :waves (default-waves)})

(defn waves-from-wind
  "Generate 4 Gerstner waves from wind direction + speed.

  Decima-style: primary wave aligned with wind, 3 subsidiary waves at a cone
  spread (+-15deg, +-30deg, +-60deg). Amplitude and wavelength scale with wind
  speed following a simplified Beaufort sea-state mapping.

  `wind-dir`: wind direction [x z] (need not be pre-normalized).
  `wind-speed`: wind speed in m/s (Beaufort ~3 = 5 m/s, ~5 = 10 m/s).
  `gust`: gust multiplier [1.0, 2.0] -- amplifies amplitude only."
  [wind-dir wind-speed gust]
  (let [len (max (sqrt* (+ (sq (nth wind-dir 0)) (sq (nth wind-dir 1)))) 1e-6)
        wd [(/ (nth wind-dir 0) len) (/ (nth wind-dir 1) len)]
        g 9.81
        u-sq (sq (max wind-speed 0.5))
        base-amp (min (max (* (/ u-sq g) 0.08) 0.1) 4.0)
        base-wavelength (min (max (* (/ u-sq g) 4.0) 8.0) 200.0)
        rot (fn [[dx dy] theta]
              (let [c (cos* theta) s (sin* theta)]
                [(- (* dx c) (* dy s)) (+ (* dx s) (* dy c))]))
        speed-for (fn [wavelength] (sqrt* (/ (* g wavelength) TAU)))
        ;; Wave 1: primary, along wind, largest
        w1 {:direction wd
            :amplitude (* base-amp gust)
            :wavelength base-wavelength
            :speed (speed-for base-wavelength)
            :steepness 0.35}
        ;; Wave 2: +30deg spread, 0.5x wavelength
        wl2 (* base-wavelength 0.5)
        w2 {:direction (rot wd 0.52)
            :amplitude (* base-amp 0.55 gust)
            :wavelength wl2
            :speed (speed-for wl2)
            :steepness 0.3}
        ;; Wave 3: -15deg spread, 0.25x wavelength (ripple)
        wl3 (* base-wavelength 0.25)
        w3 {:direction (rot wd -0.26)
            :amplitude (* base-amp 0.3 gust)
            :wavelength wl3
            :speed (speed-for wl3)
            :steepness 0.4}
        ;; Wave 4: nearly perpendicular to wind, 0.12x wavelength (fine chop)
        wl4 (* base-wavelength 0.12)
        w4 {:direction (rot wd 1.05)
            :amplitude (* base-amp 0.15 gust)
            :wavelength wl4
            :speed (speed-for wl4)
            :steepness 0.2}]
    [w1 w2 w3 w4]))

(defn generate-water-mesh
  "Generate a flat water grid mesh from a water config. Wave animation is
  expected to happen downstream (e.g. in a vertex shader).

  Returns [vertices indices] where each vertex is {:position [x y z] :uv [u v]}."
  [config]
  (let [{:keys [resolution extent sea-level]} config
        res resolution
        half (* extent 0.5)
        step (/ extent res)
        vertices (vec (for [row (range (inc res))
                             col (range (inc res))]
                         (let [x (+ (- half) (* (double col) step))
                               z (+ (- half) (* (double row) step))]
                           {:position [x sea-level z]
                            :uv [(/ (double col) res) (/ (double row) res)]})))
        row-verts (inc res)
        indices (vec (mapcat
                      (fn [row]
                        (mapcat
                         (fn [col]
                           (let [tl (+ (* row row-verts) col)
                                 tr (inc tl)
                                 bl (+ (* (inc row) row-verts) col)
                                 br (inc bl)]
                             [tl bl tr tr bl br]))
                         (range res)))
                      (range res)))]
    [vertices indices]))
