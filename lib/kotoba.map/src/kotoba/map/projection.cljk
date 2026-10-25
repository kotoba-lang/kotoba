(ns kotoba.map.projection
  "Projection-mode selection and viewport clamps.

  Ported 1:1 from `kami-map/src/lib.rs` (Rust, kotoba-lang/kami-engine), per
  ADR-2607010930 (clj-wgsl migration Phase 4): `active_projection_mode`,
  `sync_projection_mode`'s pure decision (the GPU-tile-cache invalidation
  side effect is NOT ported — see the map repo README), `cosmic_blend`,
  `cosmic_system_blend`, `clamp_lat` (the Rust `kami_geo::projection::clamp_lat`
  function itself lives in the not-yet-ported `kami-geo` crate; its Web
  Mercator formula is reproduced here as `clamp-lat` since it's a one-line
  pure function used throughout kami-map), and the zoom clamp used by
  `set_zoom`/`on_wheel`/`fit_bounds`/`frame`."
  (:require [kotoba.map.constants :as k]))

(defn clamp-lat
  "Clamp a latitude (degrees) to the Web Mercator-representable range
  `[-max-lat, max-lat]`."
  [lat]
  (max (- k/max-lat) (min k/max-lat lat)))

(defn clamp-zoom
  "Clamp a zoom level to `[zoom-min, zoom-max]`."
  [zoom]
  (max k/zoom-min (min k/zoom-max zoom)))

(defn active-projection-mode
  "Which projection mode (`:cosmic`, `:globe`, or `:flat`) is active for the
  given zoom, per the threshold constants."
  [zoom]
  (cond
    (<= zoom k/cosmic-zoom-threshold) :cosmic
    (<= zoom k/globe-zoom-threshold) :globe
    :else :flat))

(defn cosmic-blend
  "Blend factor `[0.0, 1.0]` for fading into the Cosmic scene as zoom
  decreases below `cosmic-zoom-threshold`."
  [zoom]
  (max 0.0 (min 1.0 (/ (- k/cosmic-zoom-threshold zoom) 2.6))))

(defn cosmic-system-blend
  "Blend factor `[0.0, 1.0]` for a sub-system entering view as zoom
  decreases past `enter-zoom` over `span` zoom levels."
  [zoom enter-zoom span]
  (max 0.0 (min 1.0 (/ (- enter-zoom zoom) span))))
