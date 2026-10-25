(ns kotobase-shard-index.analyze
  "Text -> terms. Same shape net-kotobase's deployed `web.search` already uses
  (ADR-2607072430): ASCII runs plus CJK bigrams, so Japanese works without a
  segmenter and without a dictionary that would have to be shipped, versioned
  and agreed on by every client.

  The analyzer is part of the wire format. A client that tokenizes differently
  from the builder looks up terms that were never written, and gets zero hits
  rather than an error. Changing it changes the index."
  (:require [kotoba.lang.text :as str]))

(def ^:private ascii-run #"[a-z0-9]+")

(defn- cjk?
  "Han, Hiragana, Katakana, and the CJK punctuation/full-width band we treat as
  word-forming. Deliberately coarse: bigrams over a coarse class still match,
  where a wrong class boundary loses the term entirely."
  [ch]
  (let [c #?(:clj (int ch) :cljs (.charCodeAt ch 0))]
    (or (<= 0x3040 c 0x30FF)                            ; kana
        (<= 0x3400 c 0x4DBF)                            ; CJK ext A
        (<= 0x4E00 c 0x9FFF)                            ; CJK unified
        (<= 0xF900 c 0xFAFF))))                         ; compat ideographs

(defn- cjk-runs
  "Maximal runs of CJK characters in `s`."
  [s]
  (->> (partition-by cjk? (seq s))
       (filter (comp cjk? first))
       (map str/join)))

(defn- bigrams
  "Overlapping 2-grams. A single character yields itself, so a one-character
  query is not silently unsearchable."
  [run]
  (if (< (count run) 2)
    [run]
    (mapv #(subs run % (+ % 2)) (range (dec (count run))))))

(defn tokenize
  "Terms in `s`, in order, with duplicates kept — term frequency is the point."
  [s]
  (when (string? s)
    (let [lowered (str/lower s)]
      (into (vec (re-seq ascii-run lowered))
            (mapcat bigrams)
            (cjk-runs lowered)))))

(defn term-freqs
  "Term -> count over `s`."
  [s]
  (frequencies (tokenize s)))

(defn doc-terms
  "Term -> weighted count for a document.

  Title terms count `title-weight` times, matching the deployed ranker's
  documented `title x3`. The weight belongs here rather than in the scorer
  because it has to be baked into the impact stored in the posting list —
  a client that re-weighted at query time would need the title, which is the
  thing we are trying not to fetch."
  ([doc] (doc-terms doc 3))
  ([{:keys [title text]} title-weight]
   (merge-with +
               (reduce-kv (fn [m t n] (assoc m t (* title-weight n))) {} (term-freqs title))
               (term-freqs text))))
