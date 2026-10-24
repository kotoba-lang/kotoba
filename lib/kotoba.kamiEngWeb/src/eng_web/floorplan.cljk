(ns eng-web.floorplan
  "Auto-floorplan input normalization + die-sizing heuristic, restored from
  `kami-eng-web/src/lib.rs` (`pnr_auto_floorplan` wasm entry point), part of
  the legacy `kami-engine` Rust workspace deleted in kotoba-lang/kami-engine
  PR #82. See ADR-2607010930 (`com-junkawasaki/root`).

  Portable: parsing input blocks with the original's `width`/`height`
  fallback (100.0) and the die-side heuristic
  (`sqrt(total_block_area * 1.5)`, a square die sized to 1.5x total block
  area). Excluded: the actual `kami_pnr::floorplan::auto_floorplan`
  placement algorithm, which lives in the unported `kami-pnr` crate.")

(defn normalize-block
  "Normalize one input block map, applying the original Rust's fallback
  defaults (`name` -> \"block\", `width`/`height` -> 100.0) for missing
  fields."
  [{:keys [name width height] :or {name "block" width 100.0 height 100.0}}]
  {:name name
   :block-type :std-cell-region
   :x 0.0
   :y 0.0
   :width width
   :height height
   :fixed false})

(defn die-size
  "Compute the square die side length for `blocks` (a seq of normalized
  blocks with `:width`/`:height`), sized to 1.5x total block area — mirrors
  `let total_area = ...; let die_side = (total_area * 1.5).sqrt();` from the
  original Rust."
  [blocks]
  (let [total-area (reduce + 0.0 (map #(* (:width %) (:height %)) blocks))]
    #?(:clj (Math/sqrt (* total-area 1.5))
       :cljs (js/Math.sqrt (* total-area 1.5)))))
