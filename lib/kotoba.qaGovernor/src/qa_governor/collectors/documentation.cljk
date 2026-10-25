(ns qa-governor.collectors.documentation
  "kotoba-lang/qa-governor — deterministic (non-LLM) documentation-coverage
  check (ADR-2607031100): what fraction of public `defn`s have a docstring,
  plus whether README.md/CHANGELOG.md exist. Pure text analysis only —
  reading files from disk is the host adapter's job
  (`qa-governor.collectors.static-analysis-shell`).

  Limitation (honest): a regex-based scan, not a real reader/AST parse. It
  will miss docstrings that contain escaped quotes, and won't understand
  reader macros. Good enough as a coverage signal, not a certifier.

  string-literal-ranges skips matches whose position falls inside a string
  literal (found via kami-engine-clj, ADR-2607032600's follow-up: a `def`
  embedding guest-language *source text* as a string — e.g. `game-prelude`
  — produced `(defn ...)`-shaped text a naive scan miscounted as 38 real
  undocumented functions in that one project). Known residual gap: this
  treats every `\\\"` as an escaped quote-inside-a-string, so it doesn't
  distinguish a standalone `\\\"` character literal (Clojure's escaped-quote
  char syntax) from an actual escape — rare in practice, and the failure
  direction (treating more text as \"inside a string\", so scanning skips it)
  only risks under-counting real defns, never over-counting fake ones,
  which is the safer of the two directions for a coverage signal."
  (:require [kotoba.lang.text :as str]))

(defn string-literal-ranges
  "[start end) 半開区間のvector: sourceの文字列リテラル(\"...\")が占める
   範囲(エスケープ\\\"を考慮した単純な文字単位スキャン)。"
  [source]
  (let [n (count source)]
    (loop [i 0 in-str? false str-start 0 ranges (transient [])]
      (if (>= i n)
        (persistent! ranges)
        (let [c (.charAt ^String source i)]
          (cond
            (and in-str? (= c \\) (< (inc i) n))
            (recur (+ i 2) in-str? str-start ranges)

            (= c \")
            (if in-str?
              (recur (inc i) false 0 (conj! ranges [str-start (inc i)]))
              (recur (inc i) true i ranges))

            :else (recur (inc i) in-str? str-start ranges)))))))

(defn- inside-any-range? [ranges pos]
  (boolean (some (fn [[s e]] (and (>= pos s) (< pos e))) ranges)))

(def ^:private defn-boundary-chars
  "`(defn`直後がこの文字集合なら本物の`(defn `境界(それ以外は`(defn-`や
   `(definitely...`のような別トークンの部分文字列)。"
  #{\space \tab \newline \return \,})

(defn parse-defn-docstring-coverage
  "source(複数ファイル分を連結した文字列でも良い)中の`(defn name ...)`
   （`defn-`は除く=公開APIのみ対象）を数え、直後にdocstring文字列がある
   ものの割合を返す。文字列リテラル内に出現した『(defn ...)らしきテキ
   スト』(docstring/コメント/def文字列に埋め込まれたソース例など)は
   出現位置がstring-literal-rangesの範囲内かで判定して除外する。
   defnが1つも無ければ100%扱い（『無いから減点』の誤検知を避ける
   ——documentation-entry側でREADME/CHANGELOGの有無は別途見る）。
   `re-matcher`(JVM専用)ではなく`str/index-of`のみで実装 — このnsは
   `.cljc`(CLJ/CLJSどちらでも使える)ので、JVM専用APIに依存しない。"
  [source]
  (let [ranges (string-literal-ranges source)
        len (count source)
        token "(defn"
        token-len (count token)]
    (loop [pos 0 total 0 documented 0]
      (let [idx (str/index-of source token pos)]
        (if (nil? idx)
          {:total total
           :documented documented
           :ratio (if (zero? total) 1.0 (/ (double documented) total))}
          (let [after (+ idx token-len)
                real-boundary? (and (< after len) (contains? defn-boundary-chars (.charAt ^String source after)))]
            (if (or (not real-boundary?) (inside-any-range? ranges idx))
              (recur after total documented)
              (let [tail (subs source after (min len (+ after 4000)))
                    m (re-find #"^[\s,]+[a-zA-Z][\w?!*+<>=-]*\s*(\"[^\"]*\")?" tail)]
                (recur after (inc total) (if (and m (some? (nth m 1))) (inc documented) documented))))))))))

(defn documentation-entry
  "source: 全.clj/.cljc/.cljsソースを連結した文字列。
   readme-exists?/changelog-exists?: プロジェクト直下に存在するか。"
  [{:keys [source readme-exists? changelog-exists?]}]
  (let [{:keys [total documented ratio]} (parse-defn-docstring-coverage source)
        doc-score (* 100 ratio)
        readme-penalty (if readme-exists? 0 20)
        changelog-penalty (if changelog-exists? 0 10)
        score (max 0 (min 100 (- doc-score readme-penalty changelog-penalty)))]
    {:category :documentation
     :score (long score)
     :evidence (str "public defns documented: " documented "/" total
                     " (" (int (* 100 ratio)) "%)"
                     (when-not readme-exists? ", README.md missing")
                     (when-not changelog-exists? ", CHANGELOG.md missing"))}))
