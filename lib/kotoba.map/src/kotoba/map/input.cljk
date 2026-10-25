(ns kotoba.map.input
  "Input handling for map interactions (pan, zoom, tilt, rotate).

  Ported 1:1 from `kami-map/src/input.rs` (Rust, kotoba-lang/kami-engine),
  per ADR-2607010930 (clj-wgsl migration Phase 4) — the Globe/Cosmic drag
  branch only (a self-contained pixel-delta -> lng/lat pan). The original
  `unsafe static mut DRAGGING` global is replaced with a plain drag-state
  map the caller threads through (`{:dragging? bool}`); `pointer-down` /
  `pointer-up` are pure state transitions.

  NOT ported: the Flat (Web Mercator) pan branch of `on_pointer_move`,
  which calls `kami_geo::projection::lng_lat_to_world_px` /
  `world_px_to_lng_lat` — those live in the not-yet-ported `kami-geo` crate.
  See the map repo README."
  (:require [kotoba.map.projection :as proj]))

(defn pointer-down
  "Begin a drag. Also clears any in-flight fly-to target, matching
  `on_pointer_down`'s `map.fly_target = None`."
  [state]
  (assoc state :dragging? true :fly-target nil))

(defn pointer-up
  "End a drag."
  [state]
  (assoc state :dragging? false))

(defn pan-globe
  "Pan `center` (`[lng lat]`) by screen-pixel delta `[dx dy]`, for the
  Globe/Cosmic projection modes, given the current viewport `width`/
  `height`. Returns the new `[lng lat]`, latitude clamped and longitude
  wrapped to `[-180, 180]`."
  [[lng lat] dx dy width height]
  (let [pixels-per-degree (max 240.0 (* (double (max width height)) 0.85))
        lng' (- lng (/ (* dx 180.0) pixels-per-degree))
        lat' (proj/clamp-lat (+ lat (/ (* dy 120.0) pixels-per-degree)))
        lng'' (cond
                (> lng' 180.0) (- lng' 360.0)
                (< lng' -180.0) (+ lng' 360.0)
                :else lng')]
    [lng'' lat']))

(defn on-pointer-move
  "Full `on_pointer_move` dispatch for Globe/Cosmic modes only. `state` is
  `{:dragging? bool :center [lng lat] :projection-mode (:globe|:cosmic|:flat)
  :width :height}`. Returns `state` with `:center` updated, or unchanged if
  not dragging or `:projection-mode` is `:flat` (unported — see namespace
  docstring)."
  [{:keys [dragging? center projection-mode width height] :as state} dx dy]
  (if (and dragging? (contains? #{:globe :cosmic} projection-mode))
    (assoc state :center (pan-globe center dx dy width height))
    state))
