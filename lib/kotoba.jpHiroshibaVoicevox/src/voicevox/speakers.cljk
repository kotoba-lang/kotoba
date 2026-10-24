(ns voicevox.speakers
  "VOICEVOX style_id catalog, emotion -> style_id switching, and the
  commercial-use credit-line renderer. Pure `.cljc`, no IO.

  Ported from `ai-gftd-project-yukkuri`'s `yukkuri.voicevox` (itself ported
  from `lg/lg_yukkuri/voicevox_client.py`), generalized to not assume the
  yukkuri project's specific env vars (VOICEVOX_SPEAKER_LEFT/RIGHT) --
  those stay in `yukkuri.channels`'s `default-identity`; this namespace
  takes explicit args so any project can reuse the same style catalog."
  (:require [kotoba.lang.text :as str]))

;; emotion -> style_id table, keyed by base style_id (2026-05 voicevox_engine 0.21).
(def emotion-style
  {2 {"normal" 2 "happy" 0 "surprised" 6 "sad" 36 "angry" 6 "whisper" 37}
   3 {"normal" 3 "happy" 1 "surprised" 7 "sad" 76 "angry" 7 "tired" 75 "whisper" 38}})

;; style_id -> official VOICEVOX character name (for commercial-use credit lines).
(def style->speaker-name
  {2 "四国めたん" 0 "四国めたん" 6 "四国めたん" 4 "四国めたん" 36 "四国めたん" 37 "四国めたん"
   3 "ずんだもん" 1 "ずんだもん" 7 "ずんだもん" 5 "ずんだもん" 22 "ずんだもん" 38 "ずんだもん"
   75 "ずんだもん" 76 "ずんだもん"
   8 "春日部つむぎ"
   10 "雨晴はう"
   9 "波音リツ"
   11 "玄野武宏" 39 "玄野武宏" 40 "玄野武宏" 41 "玄野武宏"
   12 "白上虎太郎" 32 "白上虎太郎" 33 "白上虎太郎" 34 "白上虎太郎" 35 "白上虎太郎"
   13 "青山龍星"
   14 "冥鳴ひまり"})

(defn- parse-preset-style-id [voice-preset]
  (when (and voice-preset (str/starts-with? voice-preset "voicevox:"))
    #?(:clj (try (Long/parseLong (subs voice-preset (count "voicevox:")))
                 (catch Exception _ nil))
       :cljs (let [n (js/parseInt (subs voice-preset (count "voicevox:")) 10)]
               (when-not (js/isNaN n) n)))))

(defn resolve-style-id
  "Resolve the final style_id from (L/R role) + emotion + per-line override.

  Precedence: per-line `voice-preset` (\"voicevox:<style-id>\", invalid ints
  fall back silently) > per-caller role default (`left-style`/`right-style`)
  > this namespace's fallback defaults (2/3). Emotion-driven switching
  applies on top only when `emotion-style?` is true (default false -- a
  character keeps ONE style so voice timbre stays stable across a video).

  `opts`: {:voice-preset str :left-style int :right-style int
  :emotion-style? bool}."
  [speaker emotion {:keys [voice-preset left-style right-style emotion-style?]
                     :or {left-style 2 right-style 3 emotion-style? false}}]
  (if-let [preset-id (parse-preset-style-id voice-preset)]
    preset-id
    (let [base (if (= speaker "left") left-style right-style)]
      (if-not emotion-style?
        base
        (let [table (get emotion-style base)]
          (if table (get table (or emotion "normal") base) base))))))

(defn credit-lines
  "style-ids used (a coll of ints) -> the VOICEVOX commercial-use credit
  lines required per character (dedup'd, stable order)."
  [style-ids]
  (->> style-ids
       (keep style->speaker-name)
       distinct
       (mapv (fn [name] (str "VOICEVOX:" name)))))

(def default-credit-lines
  "The credit lines for this repo's own default style_ids (2/3)."
  (credit-lines [2 3]))
