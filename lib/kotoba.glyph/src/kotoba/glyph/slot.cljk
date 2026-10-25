(ns kotoba.glyph.slot
  "Glyph identity and font-slot classification. Ports kami-text (Rust)
  `FontSlot`, `GlyphKey`, and the codepoint-range predicates
  (`prefers_cjk_font`, `prefers_emoji_font`, `is_combining_mark`,
  `is_rtl_char`) as pure `.cljc` data + functions. No font, no I/O.

  Every predicate accepts an int codepoint, a Clojure char, or a
  one-codepoint string (see `kotoba.glyph.text/char-code`) — most emoji are
  supplementary-plane codepoints (UTF-16 surrogate pairs), so a bare
  Clojure `char` cannot represent them; callers working with text should
  split it with `kotoba.glyph.text/codepoint-seq` first."
  (:require [kotoba.glyph.constants :as k]
            [kotoba.glyph.text :as text]))

(defn- in-ranges?
  "True if codepoint `cp` falls in any [lo hi] pair of `ranges`."
  [ranges cp]
  (boolean (some (fn [[lo hi]] (<= lo cp hi)) ranges)))

(defn cjk-char?
  "Mirrors `prefers_cjk_font`."
  [x]
  (in-ranges? (:cjk-ranges k/defaults) (text/char-code x)))

(defn emoji-char?
  "Mirrors `prefers_emoji_font`."
  [x]
  (in-ranges? (:emoji-ranges k/defaults) (text/char-code x)))

(defn combining-mark?
  "Mirrors `is_combining_mark`."
  [x]
  (in-ranges? (:combining-ranges k/defaults) (text/char-code x)))

(defn rtl-char?
  "Mirrors `is_rtl_char`."
  [x]
  (in-ranges? (:rtl-ranges k/defaults) (text/char-code x)))

(defn regional-indicator-char?
  "A single flag-pair codepoint (e.g. one half of the two codepoints making
  up 🇨🇭), U+1F1E6..U+1F1FF. Not present in the original Rust source
  (unicode-segmentation's grapheme clusterer handles flag pairing
  internally); added here so `kotoba.glyph.segment/graphemes` can
  approximate the same clustering without a full UAX#29 implementation."
  [x]
  (in-ranges? [(:regional-indicator-range k/defaults)] (text/char-code x)))

(defn emoji-cluster?
  "Mirrors `prefers_emoji_cluster`: true if any codepoint in the grapheme
  cluster `s` prefers the emoji font."
  [s]
  (boolean (some emoji-char? (text/codepoint-seq s))))

(defn cjk-cluster?
  [s]
  (boolean (some cjk-char? (text/codepoint-seq s))))

(defn font-slot-for-char
  "Mirrors `FontManager::slot_for_char` (minus the emoji-font-availability
  check, which is a host font-manager concern, not layout math): emoji
  takes priority over CJK, else Latin. `has-emoji-font?` defaults to true;
  pass `false` to force emoji-preferring codepoints onto the CJK/Latin
  fallback, matching the Rust fallback-when-no-emoji-font behaviour."
  ([x] (font-slot-for-char x true))
  ([x has-emoji-font?]
   (cond
     (and has-emoji-font? (emoji-char? x)) :emoji
     (cjk-char? x) :cjk
     :else :latin)))

(defn font-slot-for-cluster
  "Mirrors `font_slot_for_cluster`."
  [s]
  (cond
    (emoji-cluster? s) :emoji
    (cjk-cluster? s) :cjk
    :else :latin))

(defn glyph-key
  "Mirrors `GlyphKey::new` — identifies a glyph by (font-slot, glyph-id)."
  [font-slot glyph-id]
  {:font-slot font-slot :glyph-id glyph-id})
