(ns vegetation.lod
  "LOD: distance-based tier for vegetation instances.

  Restored from `kami-vegetation/src/lod.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  `classify-lod` is a pure function of (distance, species) -> tier
  keyword; no GPU dispatch, fully portable.")

(def lod-tiers
  "Valid LodTier values."
  #{:detail :billboard :culled})

(def ^:private detail+billboard-by-species
  "Per-species [detail-range billboard-range] thresholds (world units)."
  {:grass     [25.0 60.0]
   :fern      [40.0 90.0]
   :bush      [60.0 150.0]
   :palm-tree [200.0 600.0]
   :conifer   [180.0 500.0]})

(defn classify-lod
  "Classify `distance` (world units) for `species` (keyword id) into a
   LodTier keyword: :detail, :billboard, or :culled."
  [distance species]
  (let [[detail billboard] (get detail+billboard-by-species species)]
    (cond
      (< distance detail) :detail
      (< distance billboard) :billboard
      :else :culled)))
