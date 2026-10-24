(ns kotoba.geo.projection
  "Web Mercator (EPSG:3857) projection utilities.

  Converts between WGS84 (lng/lat degrees) and world-space coordinates used
  by a slippy/tile map renderer. World origin = (0, 0) at tile (0,0) of the
  current zoom level; one tile = `kotoba.geo.constants/tile-size-px` world
  units.

  Ported from kami-engine/kami-geo/src/projection.rs (Rust, deleted from
  the working tree pre-commit; recovered from git history). No network/IO —
  pure math.

  Data shapes (plain maps, not records, so callers can `assoc`/destructure
  freely and the namespace stays portable across JVM/cljs/SCI):
  - `LngLat`    `{:lng <deg> :lat <deg>}`
  - `WorldPx`   `{:x <px> :y <px>}`
  - `TileCoord` `{:z <zoom-int> :x <tile-x> :y <tile-y>}`"
  (:require [kotoba.lang.text :as str]
            [kotoba.geo.constants :as k]
            [kotoba.geo.math :as math]))

(defn lng-lat
  "Construct a LngLat map. Mirrors `LngLat::new`."
  [lng lat]
  {:lng lng :lat lat})

(defn world-px
  "Construct a WorldPx map."
  [x y]
  {:x x :y y})

(defn tile-coord
  "Construct a TileCoord map."
  [z x y]
  {:z z :x x :y y})

(defn lng-lat->world-px
  "Convert WGS84 → world pixel at the given (fractional) zoom level.
  Origin (0,0) = top-left of the world, +x east, +y south."
  [{:keys [lng lat]} zoom]
  (let [scale (* k/tile-size-px (math/pow 2.0 zoom))
        x (* (/ (+ lng 180.0) 360.0) scale)
        lat-rad (math/to-radians lat)
        y (* (/ (- 1.0
                    (/ (math/log (+ (math/tan lat-rad) (/ 1.0 (math/cos lat-rad))))
                       math/pi))
                 2.0)
              scale)]
    (world-px x y)))

(defn world-px->lng-lat
  "Convert world pixel → WGS84 at the given zoom level."
  [{:keys [x y]} zoom]
  (let [scale (* k/tile-size-px (math/pow 2.0 zoom))
        lng (- (* (/ x scale) 360.0) 180.0)
        n (- math/pi (* 2.0 math/pi (/ y scale)))
        lat (math/to-degrees (math/atan (* 0.5 (- (math/exp n) (math/exp (- n))))))]
    (lng-lat lng lat)))

(defn clamp-lat
  "Clamp latitude to the Web Mercator representable range."
  [lat]
  (math/clamp lat (- k/lat-clamp-deg) k/lat-clamp-deg))

(defn world-px->3d
  "Convert world pixel → 3D world position for the renderer.
  The map camera looks down the -Y axis.
  World coords: X = east, Z = south, Y = up (elevation).
  `center-px` is subtracted so the camera center sits at (0, 0, 0)."
  [{:keys [x y]} {cx :x cy :y}]
  [(- x cx) 0.0 (- y cy)])

(defn tile-origin-px
  "Top-left world pixel of this tile."
  [{:keys [x y]}]
  (world-px (* x k/tile-size-px) (* y k/tile-size-px)))

(defn tile-url
  "Build a URL from a template like
  `https://tile.openstreetmap.org/{z}/{x}/{y}.png`."
  [{:keys [z x y]} template]
  (-> template
      (str/replace "{z}" (str z))
      (str/replace "{x}" (str x))
      (str/replace "{y}" (str y))))

(defn mercator-tile-y->lat
  "Web Mercator tile row -> latitude in degrees. `y` may be fractional, and
  that is the point: a raster tile's pixel rows are linear in MERCATOR y,
  not in latitude, so anything sampling inside a tile has to come back
  through this rather than interpolating between the tile's own bounds.

  Public because `kotoba.geo.mesh` needs it per vertex. It was private, and
  `globe-tile-patch` interpolated latitude linearly instead -- which put the
  texture up to 24 degrees out of register at z0."
  [y n]
  (let [merc-n (* math/pi (- 1.0 (/ (* 2.0 y) n)))]
    (math/to-degrees (math/atan (math/sinh merc-n)))))

(defn tile-lng-lat-bounds
  "Geographic bounds of this Web Mercator tile as [west south east north]."
  [{:keys [z x y]}]
  (let [n (math/pow 2.0 z)
        west (- (* (/ x n) 360.0) 180.0)
        east (- (* (/ (inc x) n) 360.0) 180.0)
        north (mercator-tile-y->lat y n)
        south (mercator-tile-y->lat (inc y) n)]
    [west south east north]))

(defn tile-center-lng-lat
  [tile]
  (let [[west south east north] (tile-lng-lat-bounds tile)]
    (lng-lat (* (+ west east) 0.5) (* (+ south north) 0.5))))

(defn visible-tiles
  "Compute the set of tile coordinates visible in the given viewport.

  `center` — WGS84 center of the viewport (LngLat map).
  `zoom`   — fractional zoom level (0..22).
  `width`, `height` — viewport size in CSS pixels.

  Returns tiles for the integer zoom floor, padded by 1 tile each side."
  [center zoom width height]
  (let [iz (long (math/floor zoom))
        max-tile (bit-shift-left 1 iz)
        {cx :x cy :y} (lng-lat->world-px center (double iz))
        hw (/ width 2.0)
        hh (/ height 2.0)
        pad k/tile-size-px
        left (max 0.0 (- cx hw pad))
        right (min (* max-tile k/tile-size-px) (+ cx hw pad))
        top (max 0.0 (- cy hh pad))
        bottom (min (* max-tile k/tile-size-px) (+ cy hh pad))
        x-min (long (math/floor (/ left k/tile-size-px)))
        x-max (min max-tile (long (math/ceil (/ right k/tile-size-px))))
        y-min (long (math/floor (/ top k/tile-size-px)))
        y-max (min max-tile (long (math/ceil (/ bottom k/tile-size-px))))]
    (vec (for [ty (range y-min y-max)
               tx (range x-min x-max)]
           (tile-coord iz tx ty)))))
