(ns atmosphere
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-atmosphere
  Rust crate's `src/lib.rs` (deleted from kotoba-lang/kami-engine in PR #82,
  \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root). Native execution (wgpu / wasmtime /
  wasmi) stays substrate; this namespace owns the CLJC contracts / data
  interpreters / EDN IR for the domain.

  Procedural sky + atmospheric scattering: Rayleigh/Mie-style scattering
  approximation, sun position derived from time-of-day, fog, a gusting wind
  system, scrolling cloud coverage, and a combined weather snapshot. See
  `atmosphere.wind-field` (restored from `src/wind_field.rs`) for the
  per-position wind ripple sampling used to drive grass/flag/particle
  perturbation, re-exported here as `sample-wind` / `sample-gust-scalar`
  mirroring the original `pub use wind_field::{...}`.

  Vec3 values are represented as plain CLJC vectors `[x y z]`."
  (:require [atmosphere.wind-field :as wind-field]))

;; ════════════════════════════════════════════════════════════════════════
;; re-export wind-field (mirrors `pub mod wind_field; pub use wind_field::{...}`)
;; ════════════════════════════════════════════════════════════════════════

(def default-wind-field-config
  "Re-export of `atmosphere.wind-field/default-wind-field-config`."
  wind-field/default-wind-field-config)

(defn sample-wind
  "Re-export of `atmosphere.wind-field/sample-wind`."
  [x z t cfg]
  (wind-field/sample-wind x z t cfg))

(defn sample-gust-scalar
  "Re-export of `atmosphere.wind-field/sample-gust-scalar`."
  [x z t cfg]
  (wind-field/sample-gust-scalar x z t cfg))

;; ════════════════════════════════════════════════════════════════════════
;; vec3 helpers
;; ════════════════════════════════════════════════════════════════════════

(defn v3-dot
  "Dot product of two vec3 [x y z]."
  [[ax ay az] [bx by bz]]
  (+ (* ax bx) (* ay by) (* az bz)))

(defn v3-length
  "Euclidean length of a vec3 [x y z]."
  [[x y z]]
  #?(:clj  (Math/sqrt (+ (* x x) (* y y) (* z z)))
     :cljs (.sqrt js/Math (+ (* x x) (* y y) (* z z)))))

(defn v3-normalize
  "Normalize a vec3 [x y z]. Undefined (NaN/Infinity) for the zero vector,
  matching glam's `Vec3::normalize` (panics on debug, produces NaN on release —
  here we simply divide, which yields NaN for the zero-length case)."
  [v]
  (let [len (v3-length v)
        [x y z] v]
    [(/ x len) (/ y len) (/ z len)]))

(defn v3-lerp
  "Linear interpolation between vec3 `a` and `b` by `t`."
  [[ax ay az] [bx by bz] t]
  [(+ ax (* (- bx ax) t))
   (+ ay (* (- by ay) t))
   (+ az (* (- bz az) t))])

(defn v3-scale
  "Scale a vec3 [x y z] by scalar `s`."
  [[x y z] s]
  [(* x s) (* y s) (* z s)])

(defn v3-add
  "Add two vec3s."
  [[ax ay az] [bx by bz]]
  [(+ ax bx) (+ ay by) (+ az bz)])

(defn clamp01
  "Clamp `x` to [0, 1]."
  [x]
  (max 0.0 (min 1.0 x)))

(defn clamp
  "Clamp `x` to [lo, hi]."
  [x lo hi]
  (max lo (min hi x)))

;; ════════════════════════════════════════════════════════════════════════
;; SkyUniform — sky parameters for the atmosphere shader
;; ════════════════════════════════════════════════════════════════════════
;;
;; Rust `SkyUniform` struct fields → CLJC map keys:
;;   :sun-dir       [f32; 3]  — sun direction (normalized, world space)
;;   :time-of-day   f32       — time of day [0, 1] where 0.5 = noon
;;   :sun-color     [f32; 3]  — sun color (HDR, pre-multiplied by intensity)
;;   :fog-density   f32       — fog density (exponential)
;;   :fog-color     [f32; 3]  — fog color (matches horizon at current time)
;;   :sun-radius    f32       — sun disk radius (radians, ~0.01)

;; ════════════════════════════════════════════════════════════════════════
;; DayNightCycle — day/night cycle controller
;; ════════════════════════════════════════════════════════════════════════

(def tau
  "2*pi — mirrors Rust's `std::f32::consts::TAU`."
  (* 2.0 #?(:clj Math/PI :cljs js/Math.PI)))

(def default-day-night-cycle
  "Default `DayNightCycle` map. :time starts at 0.35 (morning), :period is the
  cycle length in seconds (default: 600 = 10 min)."
  {:time 0.35
   :period 600.0})

(defn day-night-tick
  "Advance a `DayNightCycle` map by `dt` seconds. Returns an updated map."
  [cycle dt]
  (update cycle :time (fn [time] (mod (+ time (/ dt (:period cycle))) 1.0))))

(defn day-night-sun-direction
  "Compute sun direction vec3 from a `DayNightCycle` map's :time.
  Sun rises at time=0.25, peaks at time=0.5, sets at time=0.75."
  [{:keys [time]}]
  (let [angle (* (- time 0.25) tau)
        y #?(:clj (Math/sin angle) :cljs (.sin js/Math angle))
        xz #?(:clj (Math/cos angle) :cljs (.cos js/Math angle))]
    (v3-normalize [(* xz 0.3) y (* xz 0.95)])))

(defn day-night-sun-color
  "Compute sun color vec3 based on time (golden hour tinting)."
  [cycle]
  (let [elevation (second (day-night-sun-direction cycle))]
    (cond
      (< elevation -0.1)
      [0.05 0.05 0.15] ; night: moonlight

      (< elevation 0.1)
      (let [t (clamp01 (/ (+ elevation 0.1) 0.2))
            sunset [1.5 0.5 0.1]
            day [1.0 0.98 0.9]]
        (v3-lerp sunset day t)) ; golden hour: warm orange -> day

      :else
      [1.0 0.98 0.9]))) ; day: warm white

(defn day-night-fog-color
  "Compute fog color vec3 (blends sky horizon color)."
  [cycle]
  (let [elevation (second (day-night-sun-direction cycle))]
    (if (< elevation 0.0)
      [0.02 0.02 0.05]
      (let [t (clamp01 elevation)
            horizon [0.7 0.8 0.95]
            zenith [0.4 0.6 0.9]]
        (v3-lerp horizon zenith (* t 0.3))))))

(defn day-night-to-uniform
  "Build a `SkyUniform` map for shader upload from a `DayNightCycle` map."
  [cycle]
  (let [dir (day-night-sun-direction cycle)
        col (day-night-sun-color cycle)
        fog (day-night-fog-color cycle)]
    {:sun-dir dir
     :time-of-day (:time cycle)
     :sun-color col
     :fog-density 0.001
     :fog-color fog
     :sun-radius 0.01}))

;; ════════════════════════════════════════════════════════════════════════
;; Rayleigh scattering approximation
;; ════════════════════════════════════════════════════════════════════════

(defn rayleigh-sky-color
  "Rayleigh scattering approximation for sky color at a view direction.
  `view-dir`, `sun-dir`, `sun-color` are vec3 [x y z]."
  [view-dir sun-dir sun-color]
  (let [cos-theta (max (v3-dot view-dir sun-dir) 0.0)
        rayleigh [0.3 0.5 1.0]
        phase (* 0.75 (+ 1.0 (* cos-theta cos-theta)))
        y (max (second view-dir) 0.0)
        gradient #?(:clj (Math/exp (* (- y) 3.0)) :cljs (.exp js/Math (* (- y) 3.0)))
        sky (v3-add (v3-scale rayleigh (* phase 0.3))
                     (v3-scale sun-color (* gradient 0.1)))
        sun-dot #?(:clj (Math/pow cos-theta 256.0) :cljs (.pow js/Math cos-theta 256.0))]
    (v3-add sky (v3-scale sun-color (* sun-dot 2.0)))))

;; ════════════════════════════════════════════════════════════════════════
;; Wind system — global wind direction + gust + Beaufort scale
;; ════════════════════════════════════════════════════════════════════════
;;
;; Rust `WindUniform` struct fields → CLJC map keys:
;;   :direction        [f32; 2]  — wind direction (normalized XZ plane)
;;   :speed            f32       — base wind speed (m/s)
;;   :gust             f32       — gust intensity [0, 1]
;;   :turbulence       f32       — turbulence frequency
;;   :gust-multiplier  f32       — current gust multiplier (time-varying)

(def default-wind-system
  "Default `WindSystem` map.
  :angle — base wind direction angle (radians from +X toward +Z), ~46° from east
  :speed — base speed (m/s); Beaufort 3-4 = gentle-moderate breeze
  :gust-intensity — gust intensity [0, 1]
  :phase — internal phase for gust oscillation"
  {:angle 0.8
   :speed 5.0
   :gust-intensity 0.3
   :phase 0.0})

(defn wind-tick
  "Advance a `WindSystem` map by `dt` seconds. Returns an updated map."
  [{:keys [phase angle] :as wind} dt]
  (let [phase' (+ phase (* dt 0.7))
        angle' (+ angle (* dt 0.01 #?(:clj (Math/sin (* phase' 0.3)) :cljs (.sin js/Math (* phase' 0.3)))))]
    (assoc wind :phase phase' :angle angle')))

(defn wind-gust-multiplier
  "Current gust multiplier (1.0 = calm, up to 1.0 + gust-intensity)."
  [{:keys [phase gust-intensity]}]
  (let [g1 (+ (* #?(:clj (Math/sin (* phase 1.7)) :cljs (.sin js/Math (* phase 1.7))) 0.5) 0.5)
        g2 (+ (* #?(:clj (Math/sin (+ (* phase 3.1) 1.3)) :cljs (.sin js/Math (+ (* phase 3.1) 1.3))) 0.3) 0.5)]
    (+ 1.0 (* gust-intensity g1 g2))))

(defn wind-direction
  "Current wind direction as a 2-vector [x z]."
  [{:keys [angle]}]
  [#?(:clj (Math/cos angle) :cljs (.cos js/Math angle))
   #?(:clj (Math/sin angle) :cljs (.sin js/Math angle))])

(defn wind-to-uniform
  "Build a `WindUniform` map for shaders from a `WindSystem` map."
  [wind]
  {:direction (wind-direction wind)
   :speed (:speed wind)
   :gust (:gust-intensity wind)
   :turbulence 1.5
   :gust-multiplier (wind-gust-multiplier wind)})

;; ════════════════════════════════════════════════════════════════════════
;; Cloud layer — scrolling noise-based cloud coverage
;; ════════════════════════════════════════════════════════════════════════
;;
;; Rust `CloudUniform` struct fields → CLJC map keys:
;;   :coverage   f32 — cloud coverage [0, 1] (0 = clear, 1 = overcast)
;;   :altitude   f32 — cloud altitude (world units above sea level)
;;   :scroll-x   f32 — cloud scroll offset x (driven by wind)
;;   :scroll-z   f32 — cloud scroll offset z (driven by wind)
;;   :density    f32 — cloud density / opacity
;;   :sharpness  f32 — cloud edge sharpness

(def default-cloud-system
  "Default `CloudSystem` map."
  {:coverage 0.45
   :altitude 300.0
   :density 0.7
   :sharpness 2.5
   :scroll-x 0.0
   :scroll-z 0.0})

(defn cloud-tick
  "Advance a `CloudSystem` map by wind. `wind` is a `WindSystem` map."
  [clouds wind dt]
  (let [[dx dz] (wind-direction wind)
        s (* (:speed wind) (wind-gust-multiplier wind) dt 0.02)]
    (-> clouds
        (update :scroll-x + (* dx s))
        (update :scroll-z + (* dz s)))))

(defn cloud-to-uniform
  "Build a `CloudUniform` map for the sky shader from a `CloudSystem` map."
  [{:keys [coverage altitude scroll-x scroll-z density sharpness]}]
  {:coverage coverage
   :altitude altitude
   :scroll-x scroll-x
   :scroll-z scroll-z
   :density density
   :sharpness sharpness})

;; ════════════════════════════════════════════════════════════════════════
;; Weather state — combined atmosphere snapshot
;; ════════════════════════════════════════════════════════════════════════

(def default-weather
  "Default `Weather` map combining day/night, wind, and clouds."
  {:day-night default-day-night-cycle
   :wind default-wind-system
   :clouds default-cloud-system})

(defn weather-tick
  "Advance a `Weather` map by `dt` seconds."
  [{:keys [day-night wind clouds] :as weather} dt]
  (let [wind' (wind-tick wind dt)]
    (assoc weather
           :day-night (day-night-tick day-night dt)
           :wind wind'
           :clouds (cloud-tick clouds wind' dt))))

(defn weather-overcast
  "Overcast preset: near-total cloud coverage, diffuse grey lighting, moderate
  wind. Matches volcanic / quarry cinematic atmosphere."
  []
  (-> default-weather
      (assoc-in [:clouds :coverage] 0.95)
      (assoc-in [:clouds :density] 1.0)
      (assoc-in [:clouds :altitude] 250.0)
      (assoc-in [:clouds :sharpness] 1.2)
      (assoc-in [:wind :speed] 8.0)
      (assoc-in [:wind :gust-intensity] 0.45)
      (assoc-in [:day-night :time] 0.42))) ; mid-morning, sun behind clouds

(defn weather-clear
  "Clear sunny preset."
  []
  (-> default-weather
      (assoc-in [:clouds :coverage] 0.25)
      (assoc-in [:clouds :density] 0.6)
      (assoc-in [:wind :speed] 4.0)
      (assoc-in [:day-night :time] 0.4)))
