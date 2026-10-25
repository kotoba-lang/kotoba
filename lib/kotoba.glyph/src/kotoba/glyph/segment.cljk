(ns kotoba.glyph.segment
  "Grapheme clustering + script/direction/font-slot run segmentation. Ports
  kami-text (Rust) `segment_text_runs`, `segment_paragraph_runs`,
  `script_for_char`/`script_for_cluster`, `direction_for_cluster`. Pure
  string math, no font, no I/O.

  Known simplification vs. the Rust original (see README `Unported`):
  `graphemes` approximates UAX#29 extended grapheme clustering (base +
  combining marks + ZWJ sequences + variation selectors + regional-
  indicator flag pairs) rather than a full table-driven implementation, and
  `segment-paragraph-runs` does not apply UAX#9 bidi *visual* reordering —
  runs are produced in logical order with correct per-run `:direction`."
  (:require [kotoba.lang.text :as str]
            [kotoba.glyph.slot :as slot]
            [kotoba.glyph.text :as text]))

(def ^:private zwj "‍")                     ; U+200D ZERO WIDTH JOINER
(def ^:private variation-selector-16 "️")   ; U+FE0F VARIATION SELECTOR-16

(defn graphemes
  "Split `s` into an approximation of extended grapheme clusters: a base
  codepoint plus any following combining marks, ZWJ-joined sequences (emoji
  ZWJ sequences, e.g. family emoji), a trailing variation selector, or a
  paired regional-indicator flag. Practical approximation, not full
  UAX#29 — unmatched combinations simply fall back to one-codepoint
  clusters."
  [s]
  (let [cps (text/codepoint-seq s)]
    (loop [cps cps out (transient []) current []]
      (cond
        (empty? cps)
        (persistent! (cond-> out (seq current) (conj! (str/join "" current))))

        (empty? current)
        (recur (rest cps) out [(first cps)])

        :else
        (let [cp (first cps)
              last-cp (peek current)]
          (cond
            (slot/combining-mark? cp)
            (recur (rest cps) out (conj current cp))

            (= cp variation-selector-16)
            (recur (rest cps) out (conj current cp))

            (= last-cp zwj)
            (recur (rest cps) out (conj current cp))

            (= cp zwj)
            (recur (rest cps) out (conj current cp))

            (and (= 1 (count current))
                 (slot/regional-indicator-char? last-cp)
                 (slot/regional-indicator-char? cp))
            (recur (rest cps) out (conj current cp))

            :else
            (recur (rest cps) (conj! out (str/join "" current)) [cp])))))))

(defn- ascii-alnum-cp? [cp]
  (or (<= 48 cp 57) (<= 65 cp 90) (<= 97 cp 122)))

(defn- ascii-punctuation-cp? [cp]
  (or (<= 33 cp 47) (<= 58 cp 64) (<= 91 cp 96) (<= 123 cp 126)))

(defn- whitespace-cp?
  "Approximates Rust `char::is_whitespace` (full Unicode White_Space
  property) with the common ASCII + general-punctuation whitespace
  codepoints — sufficient for the Latin/CJK/emoji text this segmenter
  targets."
  [cp]
  (or (= cp 32) (<= 9 cp 13) (= cp 133) (= cp 160)
      (<= 8192 cp 8202) (= cp 8232) (= cp 8233) (= cp 8239) (= cp 8287) (= cp 12288)))

(defn- latin-eligible? [x]
  (let [cp (text/char-code x)]
    (or (ascii-alnum-cp? cp) (ascii-punctuation-cp? cp) (whitespace-cp? cp))))

(defn script-for-char
  "Mirrors `script_for_char`."
  [x]
  (cond
    (slot/emoji-char? x) :emoji
    (slot/cjk-char? x) :cjk
    (latin-eligible? x) :latin
    :else :common))

(defn script-for-cluster
  "Mirrors `script_for_cluster`: script of the first non-combining-mark
  codepoint in the cluster."
  [s]
  (if-let [cp (->> (text/codepoint-seq s) (remove slot/combining-mark?) first)]
    (script-for-char cp)
    :common))

(defn direction-for-cluster
  "Mirrors `direction_for_cluster`."
  [s]
  (if (some slot/rtl-char? (text/codepoint-seq s)) :rtl :ltr))

(defn segment-paragraph-runs
  "Mirrors `segment_paragraph_runs`: group consecutive grapheme clusters
  sharing (script, direction, font-slot) into one `TextRun`
  `{:script :direction :font-slot :text}`. Logical order (see ns docstring
  re: bidi visual reordering)."
  [text]
  (if (empty? text)
    []
    (let [{:keys [runs current script direction font-slot]}
          (reduce
           (fn [{:keys [current script direction font-slot] :as acc} g]
             (let [g-script (script-for-cluster g)
                   g-direction (direction-for-cluster g)
                   g-slot (slot/font-slot-for-cluster g)]
               (if (and script (= script g-script) (= direction g-direction) (= font-slot g-slot))
                 (update acc :current conj g)
                 (cond-> acc
                   (seq current)
                   (update :runs conj {:script script :direction direction
                                        :font-slot font-slot :text (str/join "" current)})
                   true
                   (assoc :current [g] :script g-script :direction g-direction :font-slot g-slot)))))
           {:runs [] :current [] :script nil :direction nil :font-slot nil}
           (graphemes text))]
      (cond-> runs
        (seq current) (conj {:script script :direction direction
                              :font-slot font-slot :text (str/join "" current)})))))

(defn- split-inclusive-newline
  "Like Rust `str::split_inclusive('\\n')`: split `text` into segments each
  ending with `\\n` (except possibly the last)."
  [text]
  (loop [remaining text out []]
    (if (empty? remaining)
      out
      (let [idx (str/index-of remaining "\n")]
        (if idx
          (recur (subs remaining (inc idx)) (conj out (subs remaining 0 (inc idx))))
          (conj out remaining))))))

(defn segment-text-runs
  "Mirrors `segment_text_runs`: paragraph-split on `\\n`, each paragraph
  segmented by `segment-paragraph-runs`, with an explicit `{:text \"\\n\"}`
  run inserted between paragraphs."
  [text]
  (mapcat
   (fn [paragraph]
     (let [has-newline? (str/ends-with? paragraph "\n")
           body (if has-newline? (subs paragraph 0 (dec (count paragraph))) paragraph)]
       (cond-> (segment-paragraph-runs body)
         has-newline? (concat [{:script :common :direction :ltr :font-slot :latin :text "\n"}]))))
   (split-inclusive-newline text)))
