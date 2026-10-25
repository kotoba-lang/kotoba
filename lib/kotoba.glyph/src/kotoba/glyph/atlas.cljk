(ns kotoba.glyph.atlas
  "SDF/color glyph atlas rect packing. Ports the *packing* half of
  kami-text (Rust): `build_font_atlas_from_inventory` and
  `build_color_glyph_atlas_from_clusters` pack glyphs into a **uniform
  grid** (every cell the same size, derived from `font-size` alone) — this
  is not a general bin-packer, and neither was the original.

  Also ports `FontAtlas::ascii_procedural`: a fully self-contained
  procedural placeholder SDF atlas (a box-distance-field) that needs no
  font backend at all — genuinely portable CPU-side geometry, unlike the
  real SDF-from-font-outline rasterization (`ab_glyph`'s `outline_glyph`
  coverage rendering), which is a font-parsing/rasterization concern left
  to a host adapter (see README `Unported`)."
  (:require [kotoba.glyph.constants :as k]
            [kotoba.glyph.slot :as slot]))

;; ---------------------------------------------------------------------
;; Uniform-grid packing
;; ---------------------------------------------------------------------

(defn mono-cell-size
  "Mirrors the `glyph_w`/`glyph_h` cell-size computation in
  `build_font_atlas_from_inventory`."
  [font-size]
  (let [{:keys [cell-w-ratio cell-h-ratio]} (:mono-atlas k/defaults)]
    {:w (int (Math/ceil (* font-size cell-w-ratio)))
     :h (int (Math/ceil (* font-size cell-h-ratio)))}))

(defn color-cell-size
  "Mirrors the `glyph_w`/`glyph_h` cell-size computation in
  `build_color_glyph_atlas_from_clusters`."
  [font-size]
  (let [{:keys [cell-size-ratio cell-min]} (:color-atlas k/defaults)
        side (int (max (Math/ceil (* font-size cell-size-ratio)) cell-min))]
    {:w side :h side}))

(defn- pack-uniform-grid
  "Place `n` items into a `cols`-wide grid of `cell-w` x `cell-h` cells,
  row-major, mirroring the `col = i % cols; row = i / cols` placement used
  throughout kami-text's atlas builders. Returns
  `{:width :height :cols :rows :cell-w :cell-h :cells [{:index :col :row :atlas-x :atlas-y} ...]}`."
  [n cols cell-w cell-h]
  (let [n (max n 1)
        rows (int (Math/ceil (/ n (double cols))))]
    {:width (* cols cell-w)
     :height (* rows cell-h)
     :cols cols
     :rows rows
     :cell-w cell-w
     :cell-h cell-h
     :cells (mapv (fn [i]
                    (let [col (mod i cols) row (quot i cols)]
                      {:index i :col col :row row
                       :atlas-x (* col cell-w) :atlas-y (* row cell-h)}))
                  (range n))}))

(defn pack-mono-atlas
  "Pack `ordered-keys` (a deduped, caller-ordered seq of glyph keys — see
  `kotoba.glyph.slot/glyph-key`) into a mono/SDF atlas grid. Mirrors
  `build_font_atlas_from_inventory`'s packing loop (`ordered_keys`
  defaults to a single fallback key when empty, matching the Rust
  `if ordered_keys.is_empty() { push fallback }`)."
  [ordered-keys font-size]
  (let [cols (get-in k/defaults [:mono-atlas :cols])
        {:keys [w h]} (mono-cell-size font-size)
        keys* (if (seq ordered-keys) (vec ordered-keys) [(slot/glyph-key :latin 0)])
        grid (pack-uniform-grid (count keys*) cols w h)]
    (assoc grid :cells (mapv (fn [key cell] (assoc cell :key key)) keys* (:cells grid)))))

(defn pack-color-atlas
  "Pack `clusters` (a deduped, caller-ordered seq of emoji grapheme
  clusters) into a color-glyph atlas grid. Mirrors
  `build_color_glyph_atlas_from_clusters`'s packing loop. Returns `nil`
  for an empty cluster seq (mirrors `ColorGlyphAtlas::empty`'s 1x1 atlas
  being a caller concern, not packing math)."
  [clusters font-size]
  (when (seq clusters)
    (let [cols (get-in k/defaults [:color-atlas :cols])
          {:keys [w h]} (color-cell-size font-size)
          clusters* (vec clusters)
          grid (pack-uniform-grid (count clusters*) cols w h)]
      (assoc grid :cells (mapv (fn [cluster cell] (assoc cell :cluster cluster))
                                clusters* (:cells grid))))))

;; ---------------------------------------------------------------------
;; Procedural ASCII placeholder SDF atlas (no font backend required)
;; ---------------------------------------------------------------------

(defn- box-sdf-value
  "Mirrors the per-pixel box-SDF formula in `FontAtlas::ascii_procedural`:
  distance from the glyph-cell edge, biased/scaled into a `u8` coverage
  value."
  [px py glyph-w glyph-h sdf-scale sdf-bias]
  (let [dx (Math/abs (- (/ px (double glyph-w)) 0.5))
        dy (Math/abs (- (/ py (double glyph-h)) 0.5))
        d (- 0.5 (max dx dy))]
    (-> (+ (* d 255.0 sdf-scale) sdf-bias)
        (max 0.0) (min 255.0) int)))

(defn ascii-procedural-atlas
  "Mirrors `FontAtlas::ascii_procedural`: a 16x6 grid of the 96 printable
  ASCII codepoints (32..127), each cell filled with a procedurally
  generated box-distance-field — no font, no I/O, fully deterministic.
  Returns a `FontAtlas`-shaped map:
  `{:width :height :sdf-data :glyphs :glyph-index :glyph-key-index
    :line-height :ascender :font-size}`
  where `:sdf-data` is a single-channel `u8` coverage buffer (row-major,
  `idx = y * width + x`) and `:glyphs` carries per-glyph atlas rect +
  bearing/advance metadata."
  [font-size]
  (let [{:keys [cols rows first-codepoint count-glyphs cell-w-ratio glyph-h-ratio
                bearing-y-ratio advance-ratio line-height-ratio sdf-scale sdf-bias]}
        (:ascii-procedural k/defaults)
        glyph-w (int (* font-size cell-w-ratio))
        glyph-h (int (* font-size glyph-h-ratio))
        atlas-w (* cols glyph-w)
        atlas-h (* rows glyph-h)
        sdf (int-array (* atlas-w atlas-h))
        glyphs
        (mapv
         (fn [i]
           (let [ch (char (+ i first-codepoint))
                 col (mod i cols)
                 row (quot i cols)
                 ax (* col glyph-w)
                 ay (* row glyph-h)]
             (dotimes [py glyph-h]
               (dotimes [px glyph-w]
                 (let [v (box-sdf-value px py glyph-w glyph-h sdf-scale sdf-bias)
                       idx (+ (* (+ ay py) atlas-w) ax px)]
                   (when (< idx (alength sdf))
                     (aset sdf idx (int v))))))
             {:key (slot/glyph-key :latin (int ch))
              :codepoint (str ch) ; single-codepoint string, keyed like `kotoba.glyph.text/codepoint-seq` output
              :atlas-x ax :atlas-y ay :atlas-w glyph-w :atlas-h glyph-h
              :bearing-x 0.0 :bearing-y (* font-size bearing-y-ratio)
              :advance (* font-size advance-ratio)}))
         (range count-glyphs))]
    {:width atlas-w :height atlas-h
     :sdf-data (vec sdf)
     :glyphs glyphs
     :glyph-index (into {} (map (juxt :codepoint identity) glyphs))
     :glyph-key-index (into {} (map (juxt :key identity) glyphs))
     :line-height (* font-size line-height-ratio)
     :ascender (* font-size bearing-y-ratio)
     :font-size font-size}))
