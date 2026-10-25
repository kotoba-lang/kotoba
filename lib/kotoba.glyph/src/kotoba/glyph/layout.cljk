(ns kotoba.glyph.layout
  "Instanced-quad generation: converts text + an atlas into per-glyph draw
  instances (position, UV rect, size, color) a renderer can feed straight
  into an instanced quad draw call. Ports the *unshaped* fallback path of
  kami-text (Rust) `layout_text_shaped` / `layout_color_glyphs` — the
  branch that needs only per-glyph metrics already present on the atlas
  (bearing/advance/atlas-rect), not live font shaping (rustybuzz/HarfBuzz
  GPOS kerning). See README `Unported` for why real per-glyph-pair kerning
  stays a host font-shaper concern."
  (:require [kotoba.glyph.constants :as k]
            [kotoba.glyph.segment :as seg]
            [kotoba.glyph.slot :as slot]
            [kotoba.glyph.text :as text]))

(defn- uv-rect [atlas g]
  (let [aw (double (:width atlas)) ah (double (:height atlas))]
    [(/ (:atlas-x g) aw) (/ (:atlas-y g) ah)
     (/ (:atlas-w g) aw) (/ (:atlas-h g) ah)]))

(defn- layout-grapheme
  "Places one grapheme cluster's glyph(s), mirroring the inner grapheme
  loop of `layout_text_shaped`'s unshaped branch: combining marks stack on
  the cluster origin instead of advancing the cursor; the cluster then
  advances by the max of its accumulated glyph advances and a minimum, or
  by a fallback width if no glyph was found for any codepoint in it."
  [atlas color scale cursor grapheme]
  (let [{:keys [min-cluster-advance-ratio missing-glyph-advance-ratio]} (:layout k/defaults)
        cluster-origin cursor]
    (loop [cps (text/codepoint-seq grapheme)
           cluster-advance 0.0
           drew-any? false
           instances []]
      (if (empty? cps)
        (let [cursor' (if drew-any?
                        (update cursor :x + (max cluster-advance (* scale min-cluster-advance-ratio)))
                        (update cursor :x + (* scale missing-glyph-advance-ratio)))]
          [cursor' instances])
        (let [cp (first cps)]
          (if-let [g (get (:glyph-index atlas) cp)]
            (let [combining? (slot/combining-mark? cp)
                  advance-cursor (if combining? (:x cluster-origin) (+ (:x cluster-origin) cluster-advance))
                  inst {:position [(+ advance-cursor (* (:bearing-x g) scale))
                                    (- (:y cursor) (* (:bearing-y g) scale))]
                        :uv-rect (uv-rect atlas g)
                        :size [(* (:atlas-w g) scale) (* (:atlas-h g) scale)]
                        :color color}]
              (recur (rest cps)
                     (if combining? cluster-advance (+ cluster-advance (* (:advance g) scale)))
                     true
                     (conj instances inst)))
            (recur (rest cps) cluster-advance drew-any? instances)))))))

(defn layout-text
  "Mirrors `layout_text_shaped`'s unshaped-fallback branch: turns `text`
  into a vector of instanced-quad draw instances against `atlas` (any
  `{:width :height :line-height :glyph-index}` map, glyph-index keyed by
  single-codepoint string — e.g.
  `kotoba.glyph.atlas/ascii-procedural-atlas`). `origin` is `{:x :y}`,
  `color` is an opaque value copied onto every instance, `scale` a linear
  scale factor."
  [atlas text origin color scale]
  (let [line-height (* (:line-height atlas) scale)]
    (second
     (reduce
      (fn [[cursor instances] run]
        (if (empty? (:text run))
          [cursor instances]
          (reduce
           (fn [[cursor instances] grapheme]
             (if (= grapheme "\n")
               [(assoc cursor :x (:x origin) :y (+ (:y cursor) line-height)) instances]
               (let [[cursor' new-instances] (layout-grapheme atlas color scale cursor grapheme)]
                 [cursor' (into instances new-instances)])))
           [cursor instances]
           (seg/graphemes (:text run)))))
      [origin []]
      (seg/segment-text-runs text)))))

(defn layout-color-glyphs
  "Mirrors `layout_color_glyphs`: places emoji-cluster instances against a
  color-glyph atlas (`{:width :height :glyph-index}`, glyph-index keyed by
  cluster string — see `kotoba.glyph.atlas/pack-color-atlas`). Non-emoji
  graphemes (and emoji clusters missing from the atlas) advance the cursor
  by a small placeholder gap instead of drawing anything."
  [atlas text origin line-height scale]
  (let [gap-ratio (get-in k/defaults [:layout :missing-color-glyph-advance-ratio])
        aw (double (:width atlas)) ah (double (:height atlas))]
    (second
     (reduce
      (fn [[cursor instances] grapheme]
        (cond
          (= grapheme "\n")
          [(assoc cursor :x (:x origin) :y (+ (:y cursor) (* line-height scale))) instances]

          :else
          (if-let [g (and (slot/emoji-cluster? grapheme) (get (:glyph-index atlas) grapheme))]
            (let [inst {:position [(+ (:x cursor) (* (:bearing-x g) scale))
                                    (- (:y cursor) (* (:bearing-y g) scale))]
                        :size [(* (:atlas-w g) scale) (* (:atlas-h g) scale)]
                        :uv-rect [(/ (:atlas-x g) aw) (/ (:atlas-y g) ah)
                                  (/ (:atlas-w g) aw) (/ (:atlas-h g) ah)]}]
              [(update cursor :x + (* (:advance g) scale)) (conj instances inst)])
            [(update cursor :x + (* line-height gap-ratio scale)) instances])))
      [origin []]
      (seg/graphemes text)))))
