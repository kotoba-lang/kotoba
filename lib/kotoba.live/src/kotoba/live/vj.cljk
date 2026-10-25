(ns kotoba.live.vj
  "VJ deck — back-stage LED-wall visuals.

  Output is a small map (palette + pattern + intensity) the renderer feeds
  into the LED-wall pipeline. Patterns advance per-phrase; palette/intensity
  ease per-frame.")

(def patterns #{:solid :stripes :pulse :rings :scope :noise})

(def palettes
  {:neon-pink {:primary [1.0 0.2 0.6] :secondary [0.2 0.1 0.4] :accent [1.0 1.0 1.0]}
   :cool-wave {:primary [0.2 0.6 1.0] :secondary [0.05 0.1 0.3] :accent [0.7 0.95 1.0]}
   :sunset {:primary [1.0 0.5 0.2] :secondary [0.6 0.1 0.4] :accent [1.0 0.85 0.3]}
   :monochrome {:primary [1.0 1.0 1.0] :secondary [0.05 0.05 0.05] :accent [0.5 0.5 0.5]}})

(defn new-deck
  "A deck cycling `program` — a seq of `[pattern palette]` pairs, one per
  phrase. An empty program falls back to `[[:solid (:cool-wave palettes)]]`."
  [program]
  {:program (if (seq program) (vec program) [[:solid (:cool-wave palettes)]])
   :eased-intensity 0.5})

(defn default-program
  "A default 4-step program suitable for a generic 4-track set."
  []
  (new-deck [[:stripes (:cool-wave palettes)]
             [:pulse (:neon-pink palettes)]
             [:rings (:sunset palettes)]
             [:noise (:monochrome palettes)]]))

(defn frame
  "Resolve `[deck' vj-frame]` for `phase`; intensity eases toward
  `target-intensity` (0..1)."
  [deck phase target-intensity]
  (let [{:keys [program eased-intensity]} deck
        idx (mod (:phrase phase) (count program))
        [pattern palette] (nth program idx)
        alpha 0.15
        eased' (max 0.0 (min 1.0 (+ (* eased-intensity (- 1.0 alpha)) (* target-intensity alpha))))]
    [(assoc deck :eased-intensity eased')
     {:pattern pattern :palette palette :intensity eased' :bar-phase (:bar-frac phase)}]))
