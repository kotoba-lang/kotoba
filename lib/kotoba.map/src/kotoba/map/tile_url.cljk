(ns kotoba.map.tile-url
  "Tile URL templating.

  Ported 1:1 from `KamiMap::get_dem_tile_url` in `kami-map/src/lib.rs`
  (Rust, kotoba-lang/kami-engine), per ADR-2607010930 (clj-wgsl migration
  Phase 4). Pure string substitution — the general form; the Rust source
  only exposed this for DEM tiles, but the same `{z}/{x}/{y}` template
  convention is used for `default-tile-url` too (see
  `kotoba.map.constants`)."
  (:require [kotoba.lang.text :as str]))

(defn template-url
  "Substitute `{z}`, `{x}`, `{y}` placeholders in `template` with the given
  tile coordinates."
  [template z x y]
  (-> template
      (str/replace "{z}" (str z))
      (str/replace "{x}" (str x))
      (str/replace "{y}" (str y))))
