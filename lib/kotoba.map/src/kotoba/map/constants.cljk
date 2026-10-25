(ns kotoba.map.constants
  "Constants ported from hardcoded literals in kami-map/src/lib.rs (Rust).

  Canonical, tooling-readable copy: `resources/kami/map/constants.edn`. This
  namespace mirrors those values as plain defs so the portable .cljc core
  (used from JVM / ClojureScript / SCI / GraalVM) has no I/O dependency on
  reading a resource file. `constants-edn-path` below is a pure string other
  tooling can use to load the EDN independently; this namespace itself does
  not read it.")

(def constants-edn-path
  "Classpath-relative path to the canonical EDN mirror of these constants."
  "kami/map/constants.edn")

;; ---------------------------------------------------------------------------
;; Projection-mode zoom thresholds
;; ---------------------------------------------------------------------------

(def globe-zoom-threshold
  "Globe projection covers zoom [cosmic-zoom-threshold, this]. Above this,
  Flat (Web Mercator) projection takes over — user sees metro-sized areas
  where Mercator distortion is imperceptible."
  5.5)

(def cosmic-zoom-threshold
  "Below this zoom, Cosmic (solar-system-scale) projection takes over."
  0.2)

;; ---------------------------------------------------------------------------
;; Scene-scale radii
;; ---------------------------------------------------------------------------

(def globe-radius 2048.0)
(def moon-orbit-radius (* globe-radius 1.8))
(def geo-ring-radius (* globe-radius 2.6))
(def solar-system-radius (* globe-radius 38.0))
(def galaxy-radius (* globe-radius 220.0))
(def universe-radius (* globe-radius 960.0))

;; ---------------------------------------------------------------------------
;; Latitude / zoom clamp
;; ---------------------------------------------------------------------------

(def max-lat
  "Web Mercator latitude clamp: atan(sinh(pi)) in degrees."
  85.05112877980659)

(def zoom-min -1.5)
(def zoom-max 22.0)

;; ---------------------------------------------------------------------------
;; Default tile endpoints
;; ---------------------------------------------------------------------------

(def default-tile-url "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
(def default-dem-tile-url
  "https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png")

;; ---------------------------------------------------------------------------
;; Earth reference
;; ---------------------------------------------------------------------------

(def earth-radius-m 6378137.0)

;; ---------------------------------------------------------------------------
;; Degree/radian conversion.
;;
;; `Math/toRadians` and `Math/toDegrees` are `java.lang.Math` methods with no
;; JavaScript counterpart -- JS `Math` has no such function. Every other `Math/`
;; call in this repository (`sin`, `cos`, `atan2`, `asin`, `sqrt`, `pow`,
;; `abs`, `sinh`, `PI`) exists on both hosts, so these two were the whole gap.
;;
;; Measured 2026-08-25, the first time this repository's `.cljc` suites were run
;; on ClojureScript: eleven errors across `orbital` and `sphere`, all of them
;; `Function.prototype.apply was called on undefined` -- the two missing methods.
;; ---------------------------------------------------------------------------

(def radians-per-degree (/ Math/PI 180.0))

(defn to-radians
  "Degrees to radians, on both hosts."
  [degrees]
  (* degrees radians-per-degree))

(defn to-degrees
  "Radians to degrees, on both hosts."
  [radians]
  (/ radians radians-per-degree))
